"""Unit tests for the Redis Streams consumer (Task 21) using an in-memory fake."""

import pytest
from packages.config.redis import CONSUMER_GROUP, STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.orchestration import consumer as consumer_mod
from packages.orchestration.consumer import (
    consume_loop,
    ensure_consumer_groups,
    parse_read_response,
    process_message,
)
from redis.exceptions import ResponseError
from tests.fixtures.fake_redis import FakeStreamRedis
from tests.fixtures.jobs import Recorder, make_job

# --- parse_read_response -------------------------------------------------


def test_parse_resp2_str():
    resp = [[STREAM_LOW, [("1-0", {"data": "x"})]], [STREAM_HIGH, [("2-0", {"data": "y"})]]]
    entries = parse_read_response(resp)
    assert [(e.stream, e.message_id, e.fields["data"]) for e in entries] == [
        (STREAM_HIGH, "2-0", "y"),  # re-ordered by priority
        (STREAM_LOW, "1-0", "x"),
    ]


def test_parse_resp2_bytes():
    resp = [[STREAM_MEDIUM.encode(), [(b"1-0", {b"data": b"x"})]]]
    [entry] = parse_read_response(resp)
    assert entry.stream == STREAM_MEDIUM
    assert entry.message_id == "1-0"
    assert entry.fields == {"data": "x"}


def test_parse_resp3_dict_with_extra_nesting():
    resp = {STREAM_HIGH: [[("1-0", {"data": "x"}), ("2-0", {"data": "y"})]]}
    entries = parse_read_response(resp)
    assert [e.message_id for e in entries] == ["1-0", "2-0"]


@pytest.mark.parametrize("empty", [[], {}, None])
def test_parse_empty(empty):
    assert parse_read_response(empty) == []


def test_parse_entry_with_deleted_fields():
    [entry] = parse_read_response([[STREAM_LOW, [("1-0", None)]]])
    assert entry.fields == {}


# --- ensure_consumer_groups ---------------------------------------------


async def test_ensure_groups_creates_and_tolerates_busygroup():
    r = FakeStreamRedis()
    await ensure_consumer_groups(r)
    await ensure_consumer_groups(r)  # BUSYGROUP swallowed
    assert {s for s, _ in r.groups} == {STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW}


async def test_ensure_groups_propagates_other_response_errors():
    r = FakeStreamRedis()
    r.group_error = ResponseError("WRONGTYPE Operation against a key holding the wrong kind")
    with pytest.raises(ResponseError, match="WRONGTYPE"):
        await ensure_consumer_groups(r)


# --- process_message ----------------------------------------------------


async def test_process_message_acks_after_success():
    r = FakeStreamRedis()
    rec = Recorder()
    ok = await process_message(
        r, STREAM_LOW, CONSUMER_GROUP, "1-0", {b"data": make_job().model_dump_json().encode()}, rec
    )
    assert ok is True
    assert [j.delivery_id for j in rec.jobs] == ["d1"]
    assert r.acked == [(STREAM_LOW, CONSUMER_GROUP, "1-0")]


async def test_process_message_does_not_ack_when_handler_fails():
    r = FakeStreamRedis()
    rec = Recorder(fail_on={"d1"})
    ok = await process_message(
        r, STREAM_LOW, CONSUMER_GROUP, "1-0", {"data": make_job().model_dump_json()}, rec
    )
    assert ok is False
    assert r.acked == []


@pytest.mark.parametrize("fields", [{"data": "{}"}, {"data": "not json"}, {"other": "x"}, {}])
async def test_process_message_malformed_not_acked_and_does_not_raise(fields):
    r = FakeStreamRedis()
    rec = Recorder()
    assert await process_message(r, STREAM_HIGH, CONSUMER_GROUP, "1-0", fields, rec) is False
    assert r.acked == []
    assert rec.jobs == []


async def test_process_message_ack_failure_is_logged_not_raised():
    r = FakeStreamRedis()
    r.fail_acks = 1
    rec = Recorder()
    ok = await process_message(
        r, STREAM_LOW, CONSUMER_GROUP, "1-0", {"data": make_job().model_dump_json()}, rec
    )
    assert ok is False
    assert len(rec.jobs) == 1  # job ran; redelivery is idempotent


async def test_process_message_uses_traceparent_without_error():
    r = FakeStreamRedis()
    rec = Recorder()
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    job = make_job(traceparent=tp)
    assert await process_message(
        r, STREAM_LOW, CONSUMER_GROUP, "1-0", {"data": job.model_dump_json()}, rec
    )


# --- consume_loop -------------------------------------------------------


class StopAfter:
    """`running` callable that turns False after n checks."""

    def __init__(self, n: int) -> None:
        self.n = n

    def __call__(self) -> bool:
        self.n -= 1
        return self.n >= 0


@pytest.mark.parametrize("resp3", [False, True])
async def test_consume_loop_priority_order_and_acks(resp3):
    r = FakeStreamRedis(resp3=resp3)
    r.add(STREAM_LOW, make_job("low").model_dump_json())
    r.add(STREAM_MEDIUM, make_job("med").model_dump_json())
    r.add(STREAM_HIGH, make_job("high").model_dump_json())
    rec = Recorder()
    await consume_loop(r, None, "c1", rec, running=StopAfter(5))  # type: ignore[arg-type]
    assert [j.delivery_id for j in rec.jobs] == ["high", "med", "low"]
    assert len(r.acked) == 3


async def test_consume_loop_blocks_once_across_all_streams_when_idle():
    r = FakeStreamRedis()
    await consume_loop(r, None, "c1", Recorder(), running=StopAfter(1), block_ms=50)  # type: ignore[arg-type]
    blocking = [c for c in r.read_calls if c["block"]]
    non_blocking = [c for c in r.read_calls if not c["block"]]
    assert len(blocking) == 1
    assert blocking[0]["streams"] == [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]
    assert [c["streams"] for c in non_blocking] == [[STREAM_HIGH], [STREAM_MEDIUM], [STREAM_LOW]]


async def test_poison_and_failing_messages_do_not_kill_loop():
    r = FakeStreamRedis()
    r.add(STREAM_HIGH, "garbage")  # malformed
    r.add(STREAM_HIGH, make_job("boom").model_dump_json())  # handler raises
    r.add(STREAM_HIGH, make_job("good").model_dump_json())
    rec = Recorder(fail_on={"boom"})
    await consume_loop(r, None, "c1", rec, running=StopAfter(6))  # type: ignore[arg-type]
    assert [j.delivery_id for j in rec.jobs] == ["good"]
    assert [a[2] for a in r.acked] == ["3-0"]  # only the good one acked


async def test_consume_loop_survives_redis_read_errors(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(consumer_mod.asyncio, "sleep", fake_sleep)
    r = FakeStreamRedis()
    r.fail_reads = 2
    r.add(STREAM_LOW, make_job("late").model_dump_json())
    rec = Recorder()
    await consume_loop(r, None, "c1", rec, running=StopAfter(6))  # type: ignore[arg-type]
    assert [s for s in sleeps if s] == [1.0, 1.0]  # fake redis also yields via sleep(0)
    assert [j.delivery_id for j in rec.jobs] == ["late"]


async def test_consume_loop_stops_when_running_false():
    r = FakeStreamRedis()
    r.add(STREAM_LOW, make_job().model_dump_json())
    rec = Recorder()
    await consume_loop(r, None, "c1", rec, running=lambda: False)  # type: ignore[arg-type]
    assert rec.jobs == []
    assert r.read_calls == []
