"""Worker Redis behaviour against a REAL Redis (skips cleanly when unreachable).

Set ``MERIDIAN_TEST_REDIS_HOST`` / ``MERIDIAN_TEST_REDIS_PORT`` to point at a
throwaway server; the fixture uses DB 15 and flushes it.
"""

import asyncio

import pytest
from apps.worker import consumer as c
from apps.worker.janitor import run_janitor_cycle
from packages.config.redis import (
    CONSUMER_GROUP,
    STREAM_DEADLETTER,
    STREAM_HIGH,
    STREAM_LOW,
    STREAM_MEDIUM,
)
from packages.models.schemas import JobMessage
from packages.orchestration import janitor as j
from packages.orchestration.producer import enqueue_job
from redis.asyncio import Redis

from tests.fakes import eventually

pytestmark = pytest.mark.integration


def _job(delivery_id: str, priority: str = "medium") -> JobMessage:
    return JobMessage(
        delivery_id=delivery_id,
        event="pull_request",
        action="opened",
        installation_id=1,
        repository_id=2,
        repository_full_name="o/r",
        pr_number=3,
        pr_title="t",
        head_sha="h",
        base_sha="b",
        priority=priority,
        enqueued_at="2026-09-13T12:00:00Z",
    )


async def _dead_and_processed(redis: Redis, processed: list[str]) -> bool:
    return bool(await redis.xlen(STREAM_DEADLETTER)) and len(processed) == 2


async def _pending(redis: Redis, stream: str) -> list[dict[str, object]]:
    return await redis.xpending_range(stream, CONSUMER_GROUP, min="-", max="+", count=100)


# --- janitor primitives -----------------------------------------------------


async def test_xautoclaim_reply_shape_is_parsed(redis_client: Redis) -> None:
    await c.ensure_groups(redis_client)
    await redis_client.xadd(STREAM_MEDIUM, {"data": "x"})
    await redis_client.xreadgroup(CONSUMER_GROUP, "w-dead", {STREAM_MEDIUM: ">"}, count=1)
    await asyncio.sleep(0.05)
    raw = await redis_client.xautoclaim(
        STREAM_MEDIUM, CONSUMER_GROUP, "w-live", min_idle_time=10, start_id="0-0", count=10
    )
    assert isinstance(raw, list | tuple)
    cursor, entries, deleted = j.parse_xautoclaim(raw)
    assert cursor == "0-0"
    assert [fields for _id, fields in entries] == [{"data": "x"}]
    assert deleted == []


async def test_reclaim_and_dead_letter_with_real_delivery_counts(redis_client: Redis) -> None:
    await c.ensure_groups(redis_client)
    entry_id = await redis_client.xadd(STREAM_MEDIUM, {"data": "payload"})
    await redis_client.xreadgroup(CONSUMER_GROUP, "w-dead", {STREAM_MEDIUM: ">"}, count=1)
    assert await j.delivery_count(redis_client, STREAM_MEDIUM, entry_id) == 1

    # Delivery 2 and 3 happen via XAUTOCLAIM; entry is not yet exhausted at count 2.
    for expected in (2, 3):
        await asyncio.sleep(0.03)
        assert await j.dead_letter_exhausted(redis_client, STREAM_MEDIUM, min_idle_ms=10) == 0
        claimed = await j.reclaim_stalled(redis_client, STREAM_MEDIUM, "w-live", min_idle_ms=10)
        assert [e.entry_id for e in claimed] == [entry_id]
        assert await j.delivery_count(redis_client, STREAM_MEDIUM, entry_id) == expected

    await asyncio.sleep(0.03)
    assert await j.dead_letter_exhausted(redis_client, STREAM_MEDIUM, min_idle_ms=10) == 1
    assert await _pending(redis_client, STREAM_MEDIUM) == []
    dead = await redis_client.xrange(STREAM_DEADLETTER)
    assert len(dead) == 1
    assert dead[0][1]["data"] == "payload"
    assert dead[0][1]["source_id"] == entry_id
    assert dead[0][1]["deliveries"] == "3"


async def test_dead_letter_exhausted_pages_past_non_exhausted_entries(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exclusive '(' XPENDING cursor pages correctly on the real server."""
    monkeypatch.setattr(j, "_PAGE_SIZE", 2)
    await c.ensure_groups(redis_client)
    ids = [await redis_client.xadd(STREAM_LOW, {"data": str(i)}) for i in range(5)]
    await redis_client.xreadgroup(CONSUMER_GROUP, "w", {STREAM_LOW: ">"}, count=5)
    for _ in range(2):  # history reads bump the two oldest entries to 3 deliveries
        await redis_client.xreadgroup(CONSUMER_GROUP, "w", {STREAM_LOW: "0"}, count=2)
    for _ in range(2):  # XCLAIM bumps the newest entry to 3 deliveries as well
        await redis_client.xclaim(STREAM_LOW, CONSUMER_GROUP, "w", 0, [ids[4]])
    await asyncio.sleep(0.03)
    assert await j.dead_letter_exhausted(redis_client, STREAM_LOW, min_idle_ms=10) == 3
    assert [p["message_id"] for p in await _pending(redis_client, STREAM_LOW)] == ids[2:4]
    assert len(await redis_client.xrange(STREAM_DEADLETTER)) == 3


async def test_trim_never_drops_pending_or_unread(redis_client: Redis) -> None:
    await c.ensure_groups(redis_client)
    ids = [await redis_client.xadd(STREAM_HIGH, {"data": str(i)}) for i in range(12)]
    await redis_client.xreadgroup(CONSUMER_GROUP, "w", {STREAM_HIGH: ">"}, count=8)
    await redis_client.xack(STREAM_HIGH, CONSUMER_GROUP, *ids[:3])  # 3..7 pending, 8..11 unread

    trimmed = await j.trim_stream(redis_client, STREAM_HIGH, maxlen=2)
    assert trimmed == 3
    remaining = [i for i, _ in await redis_client.xrange(STREAM_HIGH)]
    assert remaining == ids[3:]
    assert len(await _pending(redis_client, STREAM_HIGH)) == 5

    # After acking everything delivered, trimming reaches maxlen but still keeps unread.
    await redis_client.xack(STREAM_HIGH, CONSUMER_GROUP, *ids[3:8])
    await j.trim_stream(redis_client, STREAM_HIGH, maxlen=2)
    assert [i for i, _ in await redis_client.xrange(STREAM_HIGH)] == ids[8:]


async def test_trim_streams_and_cycle_end_to_end(redis_client: Redis) -> None:
    await c.ensure_groups(redis_client)
    for i in range(6):
        await redis_client.xadd(STREAM_DEADLETTER, {"data": str(i)})
    result = await j.trim_streams(
        redis_client, [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW], maxlen=5, deadletter_maxlen=3
    )
    assert result[STREAM_DEADLETTER] == 3
    await run_janitor_cycle(redis_client, "w-live", min_idle_ms=10, maxlen=5)


# --- consumer ---------------------------------------------------------------


async def test_consumer_acks_after_processing_and_redelivers_failures(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    await enqueue_job(redis_client, "low", _job("low"))
    await enqueue_job(redis_client, "high", _job("high"))
    await enqueue_job(redis_client, "medium", _job("poison"))
    processed: list[str] = []
    attempts = {"poison": 0}

    async def fake_process(job: JobMessage, _sf: object, _stream: str) -> None:
        if job.delivery_id == "poison":
            attempts["poison"] += 1
            raise RuntimeError("fails")
        processed.append(job.delivery_id)

    monkeypatch.setattr(c, "process_job", fake_process)
    monkeypatch.setattr(c, "BACKLOG_INTERVAL_S", 0.0)
    stop = asyncio.Event()
    task = asyncio.create_task(c.run_consumer_loop(redis_client, None, "w1", stop))  # type: ignore[arg-type]
    try:
        await eventually(lambda: _dead_and_processed(redis_client, processed), within_s=10)
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)

    assert processed == ["high", "low"]  # strict priority
    assert attempts["poison"] == 3
    for stream in (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW):
        assert await _pending(redis_client, stream) == []  # everything acked or dead-lettered
    (dead,) = await redis_client.xrange(STREAM_DEADLETTER)
    assert dead[1]["reason"] == "max_deliveries_exceeded"


async def test_janitor_reclaim_then_consumer_backlog_redelivers_crashed_workers_job(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    await c.ensure_groups(redis_client)
    await enqueue_job(redis_client, "medium", _job("orphan"))
    # A worker reads the job and "crashes" without acking.
    await redis_client.xreadgroup(CONSUMER_GROUP, "w-crashed", {STREAM_MEDIUM: ">"}, count=1)
    await asyncio.sleep(0.05)
    await run_janitor_cycle(redis_client, "w-live", min_idle_ms=10)
    assert [p["consumer"] for p in await _pending(redis_client, STREAM_MEDIUM)] == ["w-live"]

    seen: list[str] = []

    async def fake_process(job: JobMessage, _sf: object, _stream: str) -> None:
        seen.append(job.delivery_id)

    monkeypatch.setattr(c, "process_job", fake_process)
    stop = asyncio.Event()
    task = asyncio.create_task(c.run_consumer_loop(redis_client, None, "w-live", stop))  # type: ignore[arg-type]
    try:
        await eventually(lambda: bool(seen), within_s=10)
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)
    assert seen == ["orphan"]
    assert await _pending(redis_client, STREAM_MEDIUM) == []


async def test_stop_event_interrupts_idle_blocking_read(redis_client: Redis) -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(c.run_consumer_loop(redis_client, None, "w1", stop))  # type: ignore[arg-type]
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, 3)  # BLOCK is 1s, so shutdown latency is bounded
