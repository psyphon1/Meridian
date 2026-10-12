"""Redis Streams hygiene primitives used by the worker janitor (spec §7.5, ADR-006 D6).

Three independent operations, each safe to run concurrently from several workers:

* :func:`dead_letter_exhausted` — copy entries that were already delivered
  ``max_deliveries`` times and are still unacknowledged to the dead-letter
  stream, then ``XACK`` them. Uses ``XPENDING`` delivery counters.
* :func:`reclaim_stalled` — ``XAUTOCLAIM`` entries idle longer than the
  visibility timeout to a live consumer so they are redelivered.
* :func:`trim_streams` — bound stream length without ever dropping an entry
  that is still pending (unacked) or has not been delivered yet.

All functions are verified against a real Redis (see
``tests/integration/test_janitor_redis.py``); ``redis-py`` returns lists *or*
tuples and 2- *or* 3-element ``XAUTOCLAIM`` replies depending on server
version and protocol, which :func:`parse_xautoclaim` normalises.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from packages.config.redis import CONSUMER_GROUP, STREAM_DEADLETTER
from packages.observability.logging import get_logger

log = get_logger("orchestration.janitor")

#: Deliveries after which an unacknowledged entry is dead-lettered (spec §7.1).
MAX_DELIVERIES = 3
#: An entry idle longer than this is considered stalled (visibility timeout, 5 min).
DEFAULT_VISIBILITY_TIMEOUT_MS = 300_000
#: Target stream length (spec §7.6).
DEFAULT_MAXLEN = 10_000
_PAGE_SIZE = 100
_MAX_PAGES = 100  # hard bound on one janitor pass so a huge PEL cannot starve the loop


@dataclass(frozen=True)
class StreamEntry:
    """A stream entry with text-normalised id and fields."""

    stream: str
    entry_id: str
    fields: dict[str, str]


@dataclass(frozen=True)
class PendingEntry:
    """One row of ``XPENDING`` (extended form)."""

    entry_id: str
    consumer: str
    idle_ms: int
    deliveries: int


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _normalise_fields(fields: Any) -> dict[str, str]:
    if not fields:
        return {}
    return {_text(k): _text(v) for k, v in fields.items()}


def parse_stream_id(entry_id: str) -> tuple[int, int]:
    """Parse ``"<ms>-<seq>"`` (``"<ms>"`` means seq 0) into a comparable tuple."""
    ms, _, seq = entry_id.partition("-")
    return int(ms), int(seq) if seq else 0


def _format_id(parsed: tuple[int, int]) -> str:
    return f"{parsed[0]}-{parsed[1]}"


def _is_nogroup(exc: ResponseError) -> bool:
    return "NOGROUP" in str(exc)


def parse_xautoclaim(raw: Any) -> tuple[str, list[tuple[str, dict[str, str] | None]], list[str]]:
    """Normalise an ``XAUTOCLAIM`` reply to ``(next_cursor, entries, deleted_ids)``.

    Redis < 7 returns ``[cursor, entries]``; Redis >= 7 appends the ids of
    entries that were deleted from the stream. ``redis-py`` may hand either a
    ``list`` or a ``tuple``. ``None`` fields mark entries deleted from the
    stream but still present in the PEL (Redis 6.2).
    """
    if not isinstance(raw, list | tuple) or len(raw) < 2:
        raise ValueError(f"unexpected XAUTOCLAIM reply shape: {raw!r}")
    cursor = _text(raw[0])
    entries: list[tuple[str, dict[str, str] | None]] = []
    for entry_id, fields in raw[1] or []:
        entries.append((_text(entry_id), _normalise_fields(fields) if fields else None))
    deleted = [_text(i) for i in raw[2]] if len(raw) > 2 and raw[2] else []
    return cursor, entries, deleted


async def pending_entries(
    redis: Redis,
    stream: str,
    *,
    min_idle_ms: int = 0,
    after_id: str = "-",
    count: int = _PAGE_SIZE,
    group: str = CONSUMER_GROUP,
) -> list[PendingEntry]:
    """Return up to ``count`` pending entries idle >= ``min_idle_ms``.

    ``after_id`` is an ``XPENDING`` range start; prefix with ``(`` for exclusive.
    Returns ``[]`` when the stream or group does not exist yet.
    """
    kwargs: dict[str, Any] = {}
    if min_idle_ms:
        kwargs["idle"] = min_idle_ms
    try:
        rows = await redis.xpending_range(
            stream, group, min=after_id, max="+", count=count, **kwargs
        )
    except ResponseError as exc:
        if _is_nogroup(exc):
            return []
        raise
    return [
        PendingEntry(
            entry_id=_text(row["message_id"]),
            consumer=_text(row["consumer"]),
            idle_ms=int(row["time_since_delivered"]),
            deliveries=int(row["times_delivered"]),
        )
        for row in rows
    ]


async def delivery_count(
    redis: Redis, stream: str, entry_id: str, *, group: str = CONSUMER_GROUP
) -> int:
    """Number of times ``entry_id`` has been delivered (0 if not pending)."""
    rows = await redis.xpending_range(stream, group, min=entry_id, max=entry_id, count=1)
    return int(rows[0]["times_delivered"]) if rows else 0


async def dead_letter_entry(
    redis: Redis,
    stream: str,
    entry_id: str,
    fields: dict[str, str],
    *,
    deliveries: int,
    reason: str,
    group: str = CONSUMER_GROUP,
) -> str:
    """Copy one entry to the dead-letter stream, then ``XACK`` it from ``stream``.

    XADD happens first: a crash in between leaves a duplicate dead-letter record,
    never a lost job.
    """
    record: dict[Any, Any] = dict(fields)
    record.update(
        source_stream=stream,
        source_id=entry_id,
        deliveries=str(deliveries),
        reason=reason,
    )
    dead_id = await redis.xadd(STREAM_DEADLETTER, record)
    await redis.xack(stream, group, entry_id)
    log.warning(
        "janitor.dead_lettered",
        stream=stream,
        entry_id=entry_id,
        deliveries=deliveries,
        reason=reason,
    )
    return _text(dead_id)


async def _fetch_fields(redis: Redis, stream: str, entry_id: str) -> dict[str, str]:
    rows = await redis.xrange(stream, min=entry_id, max=entry_id, count=1)
    return _normalise_fields(rows[0][1]) if rows else {}


async def dead_letter_exhausted(
    redis: Redis,
    stream: str,
    *,
    min_idle_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
    max_deliveries: int = MAX_DELIVERIES,
    group: str = CONSUMER_GROUP,
) -> int:
    """Dead-letter stalled entries delivered ``>= max_deliveries`` times.

    Must run *before* :func:`reclaim_stalled`: ``XAUTOCLAIM`` itself increments
    the delivery counter, which would otherwise dead-letter one attempt early.
    Returns the number of entries moved.
    """
    moved = 0
    cursor = "-"
    for _ in range(_MAX_PAGES):
        page = await pending_entries(
            redis, stream, min_idle_ms=min_idle_ms, after_id=cursor, count=_PAGE_SIZE, group=group
        )
        if not page:
            break
        for pending in page:
            if pending.deliveries >= max_deliveries:
                fields = await _fetch_fields(redis, stream, pending.entry_id)
                await dead_letter_entry(
                    redis,
                    stream,
                    pending.entry_id,
                    fields,
                    deliveries=pending.deliveries,
                    reason="max_deliveries_exceeded",
                    group=group,
                )
                moved += 1
        if len(page) < _PAGE_SIZE:
            break
        cursor = f"({page[-1].entry_id}"
    return moved


async def reclaim_stalled(
    redis: Redis,
    stream: str,
    consumer: str,
    *,
    min_idle_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
    group: str = CONSUMER_GROUP,
) -> list[StreamEntry]:
    """``XAUTOCLAIM`` entries idle >= ``min_idle_ms`` to ``consumer``.

    The claimed entries now sit in ``consumer``'s PEL; that consumer must read
    its backlog (``XREADGROUP ... 0``) to actually redeliver them — see
    ``apps/worker/consumer.py``. Entries whose stream record was deleted are
    ``XACK``-ed and not returned.
    """
    claimed: list[StreamEntry] = []
    cursor = "0-0"
    for _ in range(_MAX_PAGES):
        try:
            raw = await redis.xautoclaim(
                stream,
                group,
                consumer,
                min_idle_time=min_idle_ms,
                start_id=cursor,
                count=_PAGE_SIZE,
            )
        except ResponseError as exc:
            if _is_nogroup(exc):
                return claimed
            raise
        cursor, entries, deleted = parse_xautoclaim(raw)
        for entry_id, fields in entries:
            if fields is None:
                await redis.xack(stream, group, entry_id)
            else:
                claimed.append(StreamEntry(stream, entry_id, fields))
        for entry_id in deleted:
            await redis.xack(stream, group, entry_id)
        if cursor == "0-0":
            break
    if claimed:
        log.info("janitor.reclaimed", stream=stream, consumer=consumer, count=len(claimed))
    return claimed


async def trim_stream(
    redis: Redis, stream: str, *, maxlen: int = DEFAULT_MAXLEN, group: str = CONSUMER_GROUP
) -> int:
    """Trim ``stream`` to ~``maxlen`` entries without dropping live work.

    A plain ``XTRIM MAXLEN`` would delete the oldest entries even if they are
    pending (unacked, awaiting redelivery) or not yet delivered. Instead we trim
    with ``MINID`` bounded by the minimum of: the id that would keep ``maxlen``
    entries, the oldest pending id, and the first undelivered id. Streams with
    no consumer group are never trimmed. Returns the number of entries deleted.
    """
    length = await redis.xlen(stream)
    excess = length - maxlen
    if excess <= 0:
        return 0

    head = await redis.xrange(stream, min="-", max="+", count=excess + 1)
    bounds: list[tuple[int, int]] = [parse_stream_id(_text(head[-1][0]))]

    try:
        groups = await redis.xinfo_groups(stream)
    except ResponseError:
        return 0
    group_info = next((g for g in groups if _text(g.get("name")) == group), None)
    if group_info is None:
        return 0

    last_delivered = parse_stream_id(_text(group_info["last-delivered-id"]))
    # Everything strictly after last-delivered-id is unread work: keep it.
    bounds.append((last_delivered[0], last_delivered[1] + 1))
    if int(group_info.get("pending", 0)) > 0:
        summary = await redis.xpending(stream, group)
        if summary and summary.get("min"):
            bounds.append(parse_stream_id(_text(summary["min"])))

    minid = _format_id(min(bounds))
    return int(await redis.xtrim(stream, minid=minid, approximate=False))


async def trim_streams(
    redis: Redis,
    streams: Iterable[str],
    *,
    maxlen: int = DEFAULT_MAXLEN,
    deadletter_maxlen: int = DEFAULT_MAXLEN,
    group: str = CONSUMER_GROUP,
) -> dict[str, int]:
    """Trim every job stream (pending-safe) and the dead-letter stream.

    The dead-letter stream has no consumer group (humans drain it), so it uses a
    plain exact ``MAXLEN``; size it via ``deadletter_maxlen``.
    """
    result: dict[str, int] = {}
    for stream in streams:
        result[stream] = await trim_stream(redis, stream, maxlen=maxlen, group=group)
    result[STREAM_DEADLETTER] = int(
        await redis.xtrim(STREAM_DEADLETTER, maxlen=deadletter_maxlen, approximate=False)
    )
    return result
