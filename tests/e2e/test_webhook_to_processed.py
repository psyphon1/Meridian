"""E2E test — signed webhook → API → outbox row → publisher → Redis → consumer → processed.

Requires BOTH PostgreSQL (``db_engine`` fixture) and Redis (``redis_client`` fixture);
each skips cleanly when its service is unreachable. Point them at throwaway servers
with ``MERIDIAN_TEST_PG_*`` / ``MERIDIAN_TEST_REDIS_*``.

Phase 1 scope: ``on_job`` marks the ``webhook_deliveries`` row processed; it does not
create a ``review_run`` (spec §8 upserts are deferred), so that is what is asserted.
"""

import asyncio
import hashlib
import hmac
import json

import pytest
from apps.worker.consumer import run_consumer_loop
from apps.worker.outbox_publisher import publish_pending
from fastapi.testclient import TestClient
from packages.config.redis import CONSUMER_GROUP, STREAM_MEDIUM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.fakes import eventually

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_webhook_to_processed_through_real_pipeline(db_engine, redis_client, monkeypatch):
    """webhook → API → outbox (enqueued=false) → publish_pending → stream → consumer → processed."""
    import packages.models.audit
    import packages.models.identity
    import packages.models.repository
    import packages.models.review  # noqa: F401
    from packages.config.settings import get_settings
    from packages.models.audit import WebhookDelivery
    from packages.models.base import Base

    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "e2esecret")
    monkeypatch.setenv("DATABASE_URL", str(db_engine.url))

    from apps.api.main import create_app

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    payload = json.dumps(
        {
            "action": "opened",
            "number": 42,
            "installation": {"id": 12345},
            "repository": {"id": 67890, "full_name": "owner/repo"},
            "pull_request": {
                "number": 42,
                "title": "E2E test",
                "head": {"sha": "abc123"},
                "base": {"sha": "def789"},
            },
        }
    ).encode()
    sig = "sha256=" + hmac.new(b"e2esecret", payload, hashlib.sha256).hexdigest()

    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/v1/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "e2e-delivery-1",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    get_settings.cache_clear()

    # Verify the outbox row was persisted
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        deliv = (
            await session.execute(
                select(WebhookDelivery).where(WebhookDelivery.delivery_id == "e2e-delivery-1")
            )
        ).scalar_one()
        assert deliv.event == "pull_request"
        assert deliv.enqueued is False
        assert deliv.payload_size_bytes > 0

    # Outbox publisher: XADD to the medium stream and mark the row enqueued.
    result = await publish_pending(redis_client, factory)
    assert result.published == 1 and result.failed == 0
    assert await redis_client.xlen(STREAM_MEDIUM) == 1

    # Consumer: processes the job, commits, then XACKs.
    stop = asyncio.Event()
    task = asyncio.create_task(run_consumer_loop(redis_client, factory, "e2e-consumer", stop))

    async def is_processed() -> bool:
        async with factory() as session:
            row = (
                await session.execute(
                    select(WebhookDelivery).where(WebhookDelivery.delivery_id == "e2e-delivery-1")
                )
            ).scalar_one()
        return bool(row.processed)

    try:
        await eventually(is_processed, within_s=15)
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)

    async with factory() as session:
        row = (
            await session.execute(
                select(WebhookDelivery).where(WebhookDelivery.delivery_id == "e2e-delivery-1")
            )
        ).scalar_one()
    assert row.enqueued is True
    assert row.processed_at is not None
    pending = await redis_client.xpending(STREAM_MEDIUM, CONSUMER_GROUP)
    assert pending["pending"] == 0  # acked after commit
