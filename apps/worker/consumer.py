"""Worker consumer loop — processes jobs off Redis Streams (Task 26, spec §7.4/§8).

Delivery semantics (ADR-006 D6): a stream entry is ``XACK``-ed only **after** the
DB transaction that processes it has committed. A failure leaves the entry in the
PEL; it is redelivered through the backlog pass below (entries reclaimed by the
janitor land in this consumer's PEL) and dead-lettered once it has been tried
``MAX_DELIVERIES`` times. ``XACK`` is idempotent, so acking here is harmless if
``packages.orchestration.consumer.process_message`` later acks as well.

Why not ``packages.orchestration.consumer.consume_loop``? It does not expose the
stream entry id to ``on_job`` (so the wrapper cannot ack), cannot read this
consumer's PEL for redelivery, and blocks up to 5s per stream, which delays
graceful shutdown. The Redis calls are isolated in this module so switching
back is a one-function change.
"""

import asyncio
import time
from typing import Any

from opentelemetry import propagate, trace
from packages.config.redis import CONSUMER_GROUP, STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.models.audit import WebhookDelivery
from packages.models.schemas import JobMessage
from packages.observability.logging import get_logger
from packages.orchestration.janitor import MAX_DELIVERIES, dead_letter_entry, delivery_count
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.runtime import wait_or_stop

log = get_logger("worker.consumer")
_tracer = trace.get_tracer("meridian.worker")

#: Priority order — high first (spec §4.3).
PRIORITY_STREAMS = (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW)
BLOCK_MS = 1000  # bounds shutdown latency while idle
BACKLOG_INTERVAL_S = 30.0  # how often to retry this consumer's own pending entries
BACKLOG_BATCH = 10
_ERROR_BACKOFF_S = 2.0
_MAX_ERROR_BACKOFF_S = 30.0

Entry = tuple[str, str, dict[str, str] | None]  # (stream, entry_id, fields)


class DeliveryPayloadMissingError(LookupError):
    """The webhook_deliveries row referenced by a job does not exist."""


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def flatten_read(reply: Any) -> list[Entry]:
    """Flatten an ``XREADGROUP`` reply (RESP2 list or RESP3 dict) into entries."""
    if not reply:
        return []
    pairs = reply.items() if isinstance(reply, dict) else reply
    out: list[Entry] = []
    for stream, entries in pairs:
        for entry_id, fields in entries or []:
            norm = {_text(k): _text(v) for k, v in fields.items()} if fields else None
            out.append((_text(stream), _text(entry_id), norm))
    return out


async def ensure_groups(redis: Redis) -> None:
    """Create the consumer group on all priority streams (idempotent)."""
    for stream in PRIORITY_STREAMS:
        try:
            await redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


async def process_job(
    job: JobMessage,
    session_factory: async_sessionmaker[AsyncSession],
    stream: str,
) -> None:
    """Process one job inside a single DB transaction and a child trace span.

    Phase 1 scope (deliberately minimal): load the ``webhook_deliveries`` row by
    ``delivery_id`` and mark it processed. The spec §8 upserts (installation,
    repository, pull_request, review_run, audit_event) are NOT performed yet.
    """
    started = time.perf_counter()
    parent = propagate.extract({"traceparent": job.traceparent}) if job.traceparent else None
    with _tracer.start_as_current_span(
        "worker.process_job",
        context=parent,
        attributes={"meridian.stream": stream, "meridian.event": job.event},
    ):
        async with session_factory() as session, session.begin():
            deliv = (
                await session.execute(
                    select(WebhookDelivery).where(WebhookDelivery.delivery_id == job.delivery_id)
                )
            ).scalar_one_or_none()
            if deliv is None:
                raise DeliveryPayloadMissingError(job.delivery_id)
            await session.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == deliv.id)
                .values(processed=True, processed_at=func.now())
            )
        # Reached only after the transaction committed.
        log.info(
            "job_processed",
            delivery_id=job.delivery_id,
            stream=stream,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )


async def handle_entry(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    stream: str,
    entry_id: str,
    fields: dict[str, str] | None,
) -> bool:
    """Process one stream entry; ``XACK`` only after a committed success.

    Never raises for job-level problems. Returns ``True`` iff the entry was acked
    as successfully processed. Malformed entries are dead-lettered immediately
    (retrying cannot fix them); failed jobs stay pending for redelivery.
    """
    if not fields:  # entry deleted from the stream but still in the PEL
        await redis.xack(stream, CONSUMER_GROUP, entry_id)
        return False
    try:
        job = JobMessage.model_validate_json(fields.get("data", ""))
    except ValidationError:
        log.error("job.invalid", stream=stream, entry_id=entry_id)
        await dead_letter_entry(
            redis, stream, entry_id, fields, deliveries=1, reason="invalid_job_message"
        )
        return False

    try:
        await process_job(job, session_factory, stream)
    except Exception:
        # A failing job must not terminate the loop; leave it pending (no XACK).
        log.exception("job_failed", delivery_id=job.delivery_id, stream=stream, entry_id=entry_id)
        return False

    try:
        await redis.xack(stream, CONSUMER_GROUP, entry_id)
    except RedisError:
        # Stays pending; redelivery is safe because processing is idempotent.
        log.exception("job.ack_failed", delivery_id=job.delivery_id, stream=stream)
        return False
    return True


async def _backlog_pass(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
    stop: asyncio.Event,
) -> None:
    """Retry entries pending for *this* consumer (failed here or reclaimed by the janitor)."""
    for stream in PRIORITY_STREAMS:
        reply = await redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=consumer_name,
            streams={stream: "0"},
            count=BACKLOG_BATCH,
        )
        for _stream, entry_id, fields in flatten_read(reply):
            if stop.is_set():
                return
            if fields is not None:
                # The history read above counted this delivery; attempts made so far = n - 1.
                attempts = await delivery_count(redis, stream, entry_id) - 1
                if attempts >= MAX_DELIVERIES:
                    await dead_letter_entry(
                        redis,
                        stream,
                        entry_id,
                        fields,
                        deliveries=attempts,
                        reason="max_deliveries_exceeded",
                    )
                    continue
            await handle_entry(redis, session_factory, stream, entry_id, fields)


async def _read_new(redis: Redis, consumer_name: str) -> list[Entry]:
    """Read one new entry: strict priority order, then a short blocking wait on all lanes."""
    for stream in PRIORITY_STREAMS:
        reply = await redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=consumer_name,
            streams={stream: ">"},
            count=1,
        )
        entries = flatten_read(reply)
        if entries:
            return entries
    reply = await redis.xreadgroup(
        groupname=CONSUMER_GROUP,
        consumername=consumer_name,
        streams=dict.fromkeys(PRIORITY_STREAMS, ">"),
        count=1,
        block=BLOCK_MS,
    )
    return flatten_read(reply)


async def run_consumer_loop(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
    stop: asyncio.Event,
) -> None:
    """Consume until ``stop`` is set; the in-flight message is finished first."""
    await ensure_groups(redis)
    last_backlog = float("-inf")  # run a backlog pass immediately after (re)start
    failures = 0
    while not stop.is_set():
        try:
            if time.monotonic() - last_backlog >= BACKLOG_INTERVAL_S:
                last_backlog = time.monotonic()
                await _backlog_pass(redis, session_factory, consumer_name, stop)
            for stream, entry_id, fields in await _read_new(redis, consumer_name):
                await handle_entry(redis, session_factory, stream, entry_id, fields)
            failures = 0
        except Exception:
            failures += 1
            log.exception("consumer.error", consumer=consumer_name)
            delay = min(_ERROR_BACKOFF_S * 2 ** (failures - 1), _MAX_ERROR_BACKOFF_S)
            if await wait_or_stop(stop, delay):
                break
    log.info("consumer.stopped", consumer=consumer_name)
