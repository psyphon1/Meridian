"""Priority-ordered Redis Streams consumer loop (Task 21, spec §7.4, ADR-006 D3/D6).

Delivery semantics (ADR-006 D6): at-least-once. A message is ``XACK``-ed only
after ``on_job`` returned successfully, i.e. after the handler's DB transaction
committed. If the handler raises, the message is deliberately left in the
pending-entries list (PEL) so the janitor (``XAUTOCLAIM``) can reclaim it and,
after the maximum attempts, dead-letter it.

Read strategy: first a non-blocking pass over high → medium → low (strict
priority), then — only when all three are empty — a single blocking
``XREADGROUP`` across all three streams. This avoids the latency of three
sequential 5 s blocks (one per stream, in turn) while still draining higher
lanes first.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import structlog
from opentelemetry import propagate, trace
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from packages.config.redis import CONSUMER_GROUP, STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.models.schemas import JobMessage

# Priority order — high first (spec §4.3).
PRIORITY_STREAMS: tuple[str, ...] = (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW)

#: Max time (ms) a single blocking read waits; bounds graceful-stop latency.
DEFAULT_BLOCK_MS = 1000
#: Backoff (seconds) after a Redis transport error before the next attempt.
_ERROR_BACKOFF_S = 1.0

JobHandler = Callable[[JobMessage], Awaitable[None]]

_log = structlog.get_logger("orchestration.consumer")
_tracer = trace.get_tracer("meridian.orchestration.consumer")


@dataclass(frozen=True)
class StreamEntry:
    """One decoded stream entry."""

    stream: str
    message_id: str
    fields: dict[str, str]


def _text(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _is_entry(item: object) -> bool:
    """An entry is ``(id, fields)`` where id is str/bytes; a wrapper is a list of entries."""
    return (
        isinstance(item, list | tuple)
        and len(item) == 2
        and isinstance(item[0], str | bytes)
        and (item[1] is None or isinstance(item[1], Mapping))
    )


def _flatten_entries(stream: str, raw: object) -> list[StreamEntry]:
    out: list[StreamEntry] = []
    if not isinstance(raw, list | tuple):
        return out
    for item in raw:
        if _is_entry(item):
            message_id, fields = item
            decoded = {_text(k): _text(v) for k, v in (fields or {}).items()}
            out.append(StreamEntry(stream, _text(message_id), decoded))
        else:
            # RESP3 wraps the entries list in one more list level.
            out.extend(_flatten_entries(stream, item))
    return out


def parse_read_response(response: object) -> list[StreamEntry]:
    """Normalise an ``XREADGROUP`` reply into a flat, priority-ordered entry list.

    Handles:

    * RESP2 (redis-py default): ``[[stream, [(id, {field: value}), ...]], ...]``
    * RESP3: ``{stream: [[(id, {field: value}), ...]]}``
    * empty / timed-out reads (``[]``, ``{}``, ``None``)

    ``bytes`` (``decode_responses=False``) and ``str`` are both accepted.
    Entries are returned ordered high → medium → low, then by stream order.
    """
    pairs: list[tuple[str, object]] = []
    if isinstance(response, Mapping):
        pairs = [(_text(stream), entries) for stream, entries in response.items()]
    elif isinstance(response, list | tuple):
        pairs = [(_text(stream), entries) for stream, entries in response]

    entries: list[StreamEntry] = []
    for stream, raw in pairs:
        entries.extend(_flatten_entries(stream, raw))

    def rank(entry: StreamEntry) -> int:
        try:
            return PRIORITY_STREAMS.index(entry.stream)
        except ValueError:
            return len(PRIORITY_STREAMS)

    return sorted(entries, key=rank)  # stable: preserves per-stream order


async def ensure_consumer_groups(
    redis: Redis,
    group: str = CONSUMER_GROUP,
    streams: tuple[str, ...] = PRIORITY_STREAMS,
) -> None:
    """``XGROUP CREATE ... MKSTREAM`` on every stream; an existing group is fine.

    Only ``BUSYGROUP`` is swallowed — any other error (auth, OOM, wrong type)
    propagates so a misconfigured worker fails at startup, not silently.
    """
    for stream in streams:
        try:
            await redis.xgroup_create(stream, group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


def _parse_job(entry: StreamEntry) -> JobMessage:
    raw = entry.fields.get("data")
    if raw is None:
        msg = "stream entry has no 'data' field"
        raise ValueError(msg)
    return JobMessage.model_validate_json(raw)


async def process_message(
    redis: Redis,
    stream: str,
    group: str,
    message_id: str,
    fields: Mapping[Any, Any],
    on_job: JobHandler,
) -> bool:
    """Handle one stream entry and ``XACK`` it only if ``on_job`` succeeded.

    Returns ``True`` when the entry was acknowledged. Never raises for
    message-level failures (malformed payload, handler error): those are logged
    and the entry stays pending for the janitor, so one poison message cannot
    terminate the consumer. ``asyncio.CancelledError`` is not swallowed.
    """
    entry = StreamEntry(stream, message_id, {_text(k): _text(v) for k, v in (fields or {}).items()})
    try:
        job = _parse_job(entry)
    except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
        _log.error(
            "consumer.message_malformed",
            stream=stream,
            message_id=message_id,
            error=type(exc).__name__,
            detail=str(exc)[:500],
        )
        return False

    parent_ctx = propagate.extract({"traceparent": job.traceparent}) if job.traceparent else None
    with _tracer.start_as_current_span(
        "consumer.process",
        context=parent_ctx,
        attributes={
            "meridian.delivery_id": job.delivery_id,
            "meridian.stream": stream,
            "meridian.message_id": message_id,
        },
    ) as span:
        try:
            await on_job(job)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            _log.exception(
                "consumer.job_failed",
                stream=stream,
                message_id=message_id,
                delivery_id=job.delivery_id,
            )
            return False  # not acked → stays pending for XAUTOCLAIM / dead-letter

        try:
            await redis.xack(stream, group, message_id)
        except RedisError:
            # Job already committed; redelivery is idempotent (delivery_id unique).
            _log.exception(
                "consumer.ack_failed",
                stream=stream,
                message_id=message_id,
                delivery_id=job.delivery_id,
            )
            return False
    _log.info(
        "consumer.job_acked",
        stream=stream,
        message_id=message_id,
        delivery_id=job.delivery_id,
    )
    return True


async def _read(
    redis: Redis,
    group: str,
    consumer_name: str,
    streams: tuple[str, ...],
    block_ms: int | None,
) -> list[StreamEntry]:
    response = await redis.xreadgroup(
        groupname=group,
        consumername=consumer_name,
        streams=dict.fromkeys(streams, ">"),
        count=1,
        block=block_ms,
    )
    return parse_read_response(response)


async def consume_loop(
    redis: Redis,
    consumer_name: str,
    on_job: JobHandler,
    running: Callable[[], bool] = lambda: True,
    *,
    group: str = CONSUMER_GROUP,
    block_ms: int = DEFAULT_BLOCK_MS,
) -> None:
    """Main consumer loop — drains high → medium → low in strict priority order.

    ``on_job`` owns its own database transaction (it must commit before
    returning — the ack follows), so no session factory is taken. ``running``
    is polled between reads; when it returns ``False`` the loop finishes the
    entries already read, then returns (graceful drain). Transport errors are
    logged and retried with a short backoff; they never terminate the loop.
    """
    await ensure_consumer_groups(redis, group)

    while running():
        try:
            # Pass 1: non-blocking, strict priority order.
            entries: list[StreamEntry] = []
            for stream in PRIORITY_STREAMS:
                entries = await _read(redis, group, consumer_name, (stream,), None)
                if entries:
                    break
            # Pass 2: nothing ready — one blocking read across all lanes.
            if not entries:
                entries = await _read(
                    redis, group, consumer_name, PRIORITY_STREAMS, max(1, block_ms)
                )
        except RedisError:
            _log.exception("consumer.read_failed")
            await asyncio.sleep(_ERROR_BACKOFF_S)
            continue

        if not entries:
            _log.debug("consumer.idle")
            continue
        for entry in entries:
            await process_message(
                redis, entry.stream, group, entry.message_id, entry.fields, on_job
            )
