"""Consumer against a REAL Redis — verifies XREADGROUP/XACK/XAUTOCLAIM reply shapes.

Runs for RESP2 and RESP3. Skips when Redis is unreachable
(MERIDIAN_TEST_REDIS_HOST / MERIDIAN_TEST_REDIS_PORT).
"""

import asyncio

import pytest
from packages.config.redis import CONSUMER_GROUP, STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.models.schemas import JobMessage
from packages.orchestration.consumer import (
    consume_loop,
    ensure_consumer_groups,
    parse_read_response,
)
from packages.orchestration.producer import enqueue_job

from tests.fixtures.jobs import Recorder, make_job

pytestmark = pytest.mark.integration


async def _run_until(redis, handler, predicate, *, polls: int = 250) -> None:
    """Run consume_loop in the background until `predicate()` (max polls x 20 ms)."""
    state = {"stop": False}
    task = asyncio.create_task(
        consume_loop(redis, "worker-1", handler, running=lambda: not state["stop"], block_ms=100)
    )
    try:
        for _ in range(polls):
            if predicate():
                break
            await asyncio.sleep(0.02)
    finally:
        state["stop"] = True
        await asyncio.wait_for(task, timeout=3)
    assert predicate(), "condition not reached before polling limit"


async def test_ensure_groups_idempotent_on_real_redis(live_redis):
    await ensure_consumer_groups(live_redis)
    await ensure_consumer_groups(live_redis)  # BUSYGROUP is swallowed
    groups = await live_redis.xinfo_groups(STREAM_HIGH)
    assert [g["name"] for g in groups] == [CONSUMER_GROUP]


async def test_real_xreadgroup_shape_is_parsed(live_redis):
    await ensure_consumer_groups(live_redis)
    await enqueue_job(live_redis, "medium", make_job("m1"))
    raw = await live_redis.xreadgroup(
        CONSUMER_GROUP, "c", streams={STREAM_MEDIUM: ">", STREAM_LOW: ">"}, count=1
    )
    [entry] = parse_read_response(raw)
    assert entry.stream == STREAM_MEDIUM
    assert JobMessage.model_validate_json(entry.fields["data"]).delivery_id == "m1"
    # empty/timeout reply also parses
    assert (
        parse_read_response(
            await live_redis.xreadgroup(CONSUMER_GROUP, "c", streams={STREAM_LOW: ">"}, block=20)
        )
        == []
    )


async def test_consume_loop_priority_and_ack_on_real_redis(live_redis):
    await ensure_consumer_groups(live_redis)
    await enqueue_job(live_redis, "low", make_job("low"))
    await enqueue_job(live_redis, "medium", make_job("med"))
    await enqueue_job(live_redis, "high", make_job("high"))
    rec = Recorder()
    await _run_until(live_redis, rec, lambda: len(rec.jobs) == 3)
    assert [j.delivery_id for j in rec.jobs] == ["high", "med", "low"]
    for stream in (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW):
        assert (await live_redis.xpending(stream, CONSUMER_GROUP))["pending"] == 0


async def test_failed_job_stays_pending_and_is_reclaimable(live_redis):
    await ensure_consumer_groups(live_redis)
    await enqueue_job(live_redis, "high", make_job("bad"))
    await enqueue_job(live_redis, "high", make_job("ok"))
    rec = Recorder(fail_on={"bad"})
    await _run_until(live_redis, rec, lambda: len(rec.jobs) == 1)

    pending = await live_redis.xpending(STREAM_HIGH, CONSUMER_GROUP)
    assert pending["pending"] == 1  # only the failed one — NOT acked
    claimed = await live_redis.xautoclaim(
        STREAM_HIGH, CONSUMER_GROUP, "janitor", min_idle_time=0, count=10
    )
    entries = claimed[1]
    assert len(entries) == 1
    assert JobMessage.model_validate_json(entries[0][1]["data"]).delivery_id == "bad"


async def test_poison_message_on_real_redis_does_not_stop_consumer(live_redis):
    await ensure_consumer_groups(live_redis)
    await live_redis.xadd(STREAM_HIGH, {"data": "{not-json"})
    await live_redis.xadd(STREAM_HIGH, {"unexpected": "field"})
    await enqueue_job(live_redis, "high", make_job("after-poison"))
    rec = Recorder()
    await _run_until(live_redis, rec, lambda: len(rec.jobs) == 1)
    assert rec.jobs[0].delivery_id == "after-poison"
    assert (await live_redis.xpending(STREAM_HIGH, CONSUMER_GROUP))["pending"] == 2
