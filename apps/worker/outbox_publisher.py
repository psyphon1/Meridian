"""Transactional outbox publisher — webhook_deliveries → Redis Streams (Task 27)."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from packages.models.audit import WebhookDelivery
from packages.models.schemas import JobMessage
from packages.observability.logging import get_logger
from packages.observability.tracing import inject_traceparent
from packages.orchestration.producer import enqueue_job
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("worker.outbox")


def build_job_message(deliv: WebhookDelivery) -> JobMessage:
    """Construct a JobMessage reference from a webhook_delivery row."""
    payload = deliv.payload
    pr: dict[str, Any] = payload.get("pull_request", {})
    repo: dict[str, Any] = payload.get("repository", {})
    inst: dict[str, Any] = payload.get("installation", {})
    return JobMessage(
        delivery_id=deliv.delivery_id,
        event=deliv.event,
        action=deliv.action,
        installation_id=inst.get("id", 0),
        repository_id=repo.get("id", 0),
        repository_full_name=repo.get("full_name", ""),
        pr_number=pr.get("number", 0),
        pr_title=pr.get("title", ""),
        head_sha=pr.get("head", {}).get("sha", ""),
        base_sha=pr.get("base", {}).get("sha", ""),
        priority="medium",  # Phase 1: default to medium
        traceparent=inject_traceparent(),
        enqueued_at=datetime.now(UTC).isoformat(),
    )


async def publish_pending(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Poll webhook_deliveries for enqueued=false, XADD, mark enqueued=true.

    Returns the number of rows published.
    """
    published = 0
    async with session_factory() as session, session.begin():
        rows = (
            (
                await session.execute(
                    select(WebhookDelivery)
                    .where(WebhookDelivery.enqueued.is_(False))
                    .order_by(WebhookDelivery.created_at)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        for deliv in rows:
            msg = build_job_message(deliv)
            await enqueue_job(redis, msg.priority, msg)
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(enqueued=True, enqueued_at=func.now())
            )
            published += 1

    if published:
        log.info("outbox.published", count=published)
    return published


async def run_outbox_publisher(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Main outbox publisher loop — polls every ~1s."""
    while True:
        try:
            count = await publish_pending(redis, session_factory)
            if count == 0:
                await asyncio.sleep(1)
        except Exception:
            log.exception("outbox.error")
            await asyncio.sleep(5)
