"""Integration tests for the ingestion service (Task 22).

Requires PostgreSQL (advisory locks + JSONB) — uses the ephemeral
per-test database fixture, which skips cleanly when PG is unreachable.
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = pytest.mark.integration

PAYLOAD = json.dumps(
    {
        "action": "opened",
        "number": 42,
        "installation": {"id": 12345},
        "repository": {"id": 67890, "full_name": "owner/repo"},
        "pull_request": {
            "number": 42,
            "title": "Add X",
            "head": {"sha": "abc123"},
            "base": {"sha": "def789"},
        },
    }
).encode()


def _make_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_ingest_creates_delivery(db_engine):
    import packages.models.audit
    import packages.models.identity
    import packages.models.repository
    import packages.models.review  # noqa: F401
    from packages.models.audit import WebhookDelivery
    from packages.models.base import Base
    from packages.orchestration.ingestion import ingest_webhook

    factory = _make_factory(db_engine)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session, session.begin():
        result = await ingest_webhook(
            session,
            "delivery-uuid-1",
            "pull_request",
            "opened",
            PAYLOAD,
        )
    assert result.status == "accepted"
    assert result.delivery_id == "delivery-uuid-1"

    async with factory() as session:
        deliv = (
            await session.execute(
                select(WebhookDelivery).where(WebhookDelivery.delivery_id == "delivery-uuid-1")
            )
        ).scalar_one()
        assert deliv.event == "pull_request"
        assert deliv.enqueued is False


@pytest.mark.asyncio
async def test_ingest_idempotent_replay(db_engine):
    import packages.models.audit
    import packages.models.identity
    import packages.models.repository
    import packages.models.review  # noqa: F401
    from packages.models.audit import WebhookDelivery
    from packages.models.base import Base
    from packages.orchestration.ingestion import ingest_webhook

    factory = _make_factory(db_engine)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as s, s.begin():
        r1 = await ingest_webhook(s, "dup-1", "pull_request", "opened", PAYLOAD)
    async with factory() as s, s.begin():
        r2 = await ingest_webhook(s, "dup-1", "pull_request", "opened", PAYLOAD)

    assert r1.status == "accepted"
    assert r2.status == "replayed"

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(WebhookDelivery).where(WebhookDelivery.delivery_id == "dup-1")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
