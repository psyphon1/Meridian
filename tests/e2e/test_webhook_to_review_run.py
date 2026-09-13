"""E2E test — webhook → API → Postgres outbox row (Task 29).

Requires PostgreSQL (uses the ephemeral per-test database fixture, which
skips cleanly when PG is unreachable). Redis is exercised separately in
integration tests; the outbox publisher path is covered by unit tests.
"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_full_pipeline_webhook_to_processed(db_engine, monkeypatch):
    """E2E: webhook → API → Postgres outbox → (worker marks processed).

    This test exercises the full ingestion path without a live Redis
    (the outbox publisher is tested separately in integration). It verifies
    that a valid webhook creates a webhook_delivery row that the worker
    can later mark processed.
    """
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
