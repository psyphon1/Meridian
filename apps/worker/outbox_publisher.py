"""Transactional outbox publisher — webhook_deliveries → Redis Streams (Task 27, ADR-006).

Per-row isolation: one bad row never blocks or rolls back the others.

* Build/validation failure (permanent): logged with ``delivery_id`` and quarantined
  for this process lifetime. ``webhook_deliveries`` has no attempt/failed column
  (a schema change needs its own migration + ADR), so quarantine is in-memory;
  the row stays ``enqueued=false`` and is retried after a worker restart.
* ``XADD`` failure (usually transient): logged, row left ``enqueued=false`` and
  retried on the next poll; later rows are still attempted.

Delivery is at-least-once: if the DB commit fails after some ``XADD`` calls, those
rows are re-published; the consumer is idempotent on ``delivery_id`` (spec §7.6).

Trace context: the API's trace context is not persisted on ``webhook_deliveries``
(also needs a migration), so the job's ``traceparent`` is rooted at the
``outbox.publish`` span created here. Linking back to ``webhook.receive`` requires
persisting the API ``traceparent`` — flagged for the owner.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from packages.models.audit import WebhookDelivery
from packages.models.schemas import JobMessage
from packages.observability.logging import get_logger
from packages.observability.tracing import inject_traceparent
from packages.orchestration.producer import enqueue_job
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.runtime import wait_or_stop

log = get_logger("worker.outbox")
_tracer = trace.get_tracer("meridian.worker")

BATCH_SIZE = 100
POLL_INTERVAL_S = 1.0
_ERROR_BACKOFF_S = 2.0
_MAX_ERROR_BACKOFF_S = 60.0
MAX_QUARANTINE = 1000


@dataclass(frozen=True)
class PublishResult:
    """Outcome of one :func:`publish_pending` pass."""

    published: int
    failed: int


def _obj(parent: Any, key: str) -> dict[str, Any]:
    value = parent.get(key) if isinstance(parent, dict) else None
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def build_job_message(deliv: WebhookDelivery) -> JobMessage:
    """Construct a JobMessage reference from a webhook_delivery row.

    Tolerates JSON ``null`` / missing / wrongly-typed fields (e.g. ``title: null``)
    by falling back to empty values rather than failing the whole row.
    """
    payload = deliv.payload
    pr = _obj(payload, "pull_request")
    repo = _obj(payload, "repository")
    inst = _obj(payload, "installation")
    return JobMessage(
        delivery_id=deliv.delivery_id,
        event=deliv.event,
        action=deliv.action,
        installation_id=_int(inst.get("id")),
        repository_id=_int(repo.get("id")),
        repository_full_name=_str(repo.get("full_name")),
        pr_number=_int(pr.get("number")),
        pr_title=_str(pr.get("title")),
        head_sha=_str(_obj(pr, "head").get("sha")),
        base_sha=_str(_obj(pr, "base").get("sha")),
        priority="medium",  # Phase 1: default to medium
        traceparent=inject_traceparent(),
        enqueued_at=datetime.now(UTC).isoformat(),
    )


async def publish_pending(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    quarantine: set[str] | None = None,
) -> PublishResult:
    """Poll ``enqueued=false`` rows, XADD each, mark successes ``enqueued=true``.

    ``quarantine`` is the caller-owned set of delivery ids that failed permanently;
    they are excluded from the query and extended by this call.
    """
    quarantine = quarantine if quarantine is not None else set()
    published = 0
    failed = 0
    query = select(WebhookDelivery).where(WebhookDelivery.enqueued.is_(False))
    if quarantine:
        query = query.where(WebhookDelivery.delivery_id.not_in(quarantine))
    async with session_factory() as session, session.begin():
        rows = (
            (
                await session.execute(
                    query.order_by(WebhookDelivery.created_at)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        for deliv in rows:
            delivery_id = deliv.delivery_id
            try:
                with _tracer.start_as_current_span("outbox.publish"):
                    msg = build_job_message(deliv)
            except (ValueError, TypeError):
                failed += 1
                if len(quarantine) < MAX_QUARANTINE:
                    quarantine.add(delivery_id)
                log.exception("outbox.row_invalid", delivery_id=delivery_id)
                continue
            try:
                await enqueue_job(redis, msg.priority, msg)
            except (RedisError, OSError):
                failed += 1
                log.exception("outbox.xadd_failed", delivery_id=delivery_id)
                continue
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(enqueued=True, enqueued_at=func.now())
            )
            published += 1

    if published or failed:
        log.info("outbox.published", count=published, failed=failed)
    return PublishResult(published=published, failed=failed)


async def run_outbox_publisher(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    stop: asyncio.Event,
) -> None:
    """Poll every ~1s until ``stop`` is set; back off exponentially on errors."""
    quarantine: set[str] = set()
    consecutive_errors = 0
    while not stop.is_set():
        try:
            result = await publish_pending(redis, session_factory, quarantine)
        except Exception:
            consecutive_errors += 1
            log.exception("outbox.error", consecutive_errors=consecutive_errors)
            delay = min(_ERROR_BACKOFF_S * 2 ** (consecutive_errors - 1), _MAX_ERROR_BACKOFF_S)
        else:
            consecutive_errors = 0
            if result.failed:
                delay = _ERROR_BACKOFF_S
            elif result.published >= BATCH_SIZE:
                delay = 0.0  # backlog remains; do not idle
            else:
                delay = POLL_INTERVAL_S
        if await wait_or_stop(stop, delay):
            break
    log.info("outbox.stopped")
