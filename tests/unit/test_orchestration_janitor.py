"""Unit tests for packages.orchestration.janitor against an in-memory Redis fake."""

import pytest
from packages.config.redis import CONSUMER_GROUP, STREAM_DEADLETTER, STREAM_MEDIUM
from packages.orchestration import janitor as j
from redis.exceptions import ResponseError
from tests.fakes import FakeRedis

STREAM = STREAM_MEDIUM


async def _setup(n: int = 3) -> tuple[FakeRedis, list[str]]:
    r = FakeRedis()
    await r.xgroup_create(STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    ids = [await r.xadd(STREAM, {"data": f"job{i}"}) for i in range(n)]
    return r, ids


@pytest.mark.parametrize("shape", ["list3", "tuple2", "tuple3"])
async def test_parse_xautoclaim_handles_list_and_tuple_shapes(shape: str) -> None:
    r = FakeRedis(autoclaim_shape=shape)
    await r.xgroup_create(STREAM, CONSUMER_GROUP, id="0")
    await r.xadd(STREAM, {"data": "a"})
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    r.advance(10)
    raw = await r.xautoclaim(STREAM, CONSUMER_GROUP, "c2", min_idle_time=5)
    cursor, entries, deleted = j.parse_xautoclaim(raw)
    assert cursor == "0-0"
    assert [e[1] for e in entries] == [{"data": "a"}]
    assert deleted == []


def test_parse_xautoclaim_bytes_and_deleted_ids() -> None:
    raw = [b"0-0", [(b"1-1", {b"data": b"x"}), (b"1-2", None)], [b"1-3"]]
    cursor, entries, deleted = j.parse_xautoclaim(raw)
    assert (cursor, deleted) == ("0-0", ["1-3"])
    assert entries == [("1-1", {"data": "x"}), ("1-2", None)]


def test_parse_xautoclaim_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="unexpected XAUTOCLAIM"):
        j.parse_xautoclaim("nope")


def test_parse_stream_id() -> None:
    assert j.parse_stream_id("12-3") == (12, 3)
    assert j.parse_stream_id("12") == (12, 0)


async def test_reclaim_stalled_moves_idle_entries_to_consumer() -> None:
    r, ids = await _setup(2)
    await r.xreadgroup(CONSUMER_GROUP, "dead-worker", {STREAM: ">"}, count=2)
    r.advance(1000)
    claimed = await j.reclaim_stalled(r, STREAM, "live-worker", min_idle_ms=500)
    assert [c.entry_id for c in claimed] == ids
    assert claimed[0].fields == {"data": "job0"}
    rows = await r.xpending_range(STREAM, CONSUMER_GROUP)
    assert {row["consumer"] for row in rows} == {"live-worker"}


async def test_reclaim_stalled_ignores_fresh_entries_and_missing_group() -> None:
    r, _ = await _setup(1)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    assert await j.reclaim_stalled(r, STREAM, "c2", min_idle_ms=60_000) == []
    assert await j.reclaim_stalled(FakeRedis(), STREAM, "c2") == []


async def test_reclaim_acks_entries_deleted_from_stream() -> None:
    r, _ids = await _setup(1)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    r.streams[STREAM].clear()  # entry trimmed while pending
    r.advance(1000)
    assert await j.reclaim_stalled(r, STREAM, "c2", min_idle_ms=10) == []
    assert await r.xpending_range(STREAM, CONSUMER_GROUP) == []


async def test_dead_letter_exhausted_copies_and_acks_only_exhausted() -> None:
    r, ids = await _setup(2)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"}, count=2)
    r.advance(1000)
    # Entry 0 gets redelivered twice more (count 3); entry 1 stays at 1.
    for _ in range(2):
        r.groups[STREAM][CONSUMER_GROUP]["pending"][ids[0]][2] += 1
    moved = await j.dead_letter_exhausted(r, STREAM, min_idle_ms=500)
    assert moved == 1
    dead = r.streams[STREAM_DEADLETTER]
    assert len(dead) == 1
    fields = dead[0][1]
    assert fields["data"] == "job0"
    assert fields["source_id"] == ids[0]
    assert fields["source_stream"] == STREAM
    assert fields["deliveries"] == "3"
    pending = {p["message_id"] for p in await r.xpending_range(STREAM, CONSUMER_GROUP)}
    assert pending == {ids[1]}


async def test_dead_letter_skips_entries_not_yet_idle() -> None:
    r, ids = await _setup(1)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    r.groups[STREAM][CONSUMER_GROUP]["pending"][ids[0]][2] = 5
    assert await j.dead_letter_exhausted(r, STREAM, min_idle_ms=60_000) == 0


async def test_dead_letter_runs_before_reclaim_so_counts_are_not_inflated() -> None:
    """Two prior deliveries + one reclaim = third attempt, NOT dead-lettered early."""
    r, ids = await _setup(1)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    r.groups[STREAM][CONSUMER_GROUP]["pending"][ids[0]][2] = 2
    r.advance(1000)
    assert await j.dead_letter_exhausted(r, STREAM, min_idle_ms=500) == 0
    claimed = await j.reclaim_stalled(r, STREAM, "c2", min_idle_ms=500)
    assert len(claimed) == 1
    assert await j.delivery_count(r, STREAM, ids[0]) == 3
    r.advance(1000)
    assert await j.dead_letter_exhausted(r, STREAM, min_idle_ms=500) == 1


async def test_dead_letter_handles_trimmed_source_entry() -> None:
    r, ids = await _setup(1)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"})
    r.groups[STREAM][CONSUMER_GROUP]["pending"][ids[0]][2] = 3
    r.streams[STREAM].clear()
    r.advance(1000)
    assert await j.dead_letter_exhausted(r, STREAM, min_idle_ms=500) == 1
    assert r.streams[STREAM_DEADLETTER][0][1]["source_id"] == ids[0]


async def test_dead_letter_missing_group_is_noop() -> None:
    assert await j.dead_letter_exhausted(FakeRedis(), STREAM) == 0
    assert await j.delivery_count(await _setup_one(), STREAM, "9-9") == 0


async def _setup_one() -> FakeRedis:
    r, _ = await _setup(1)
    return r


async def test_pending_entries_propagates_non_nogroup_errors() -> None:
    class Boom(FakeRedis):
        async def xpending_range(self, *a: object, **k: object) -> list[dict[str, object]]:
            raise ResponseError("ERR something else")

    with pytest.raises(ResponseError):
        await j.pending_entries(Boom(), STREAM)


async def test_trim_stream_noop_when_under_maxlen() -> None:
    r, _ = await _setup(3)
    assert await j.trim_stream(r, STREAM, maxlen=10) == 0
    assert r.xtrim_calls == []


async def test_trim_stream_never_drops_pending_or_undelivered() -> None:
    r, ids = await _setup(10)
    # deliver first 6; ack 0..2, leaving 3..5 pending; 6..9 undelivered.
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"}, count=6)
    await r.xack(STREAM, CONSUMER_GROUP, *ids[:3])
    trimmed = await j.trim_stream(r, STREAM, maxlen=2)
    assert trimmed == 3  # only the acked prefix
    assert [e[0] for e in r.streams[STREAM]] == ids[3:]


async def test_trim_stream_trims_to_maxlen_when_everything_acked() -> None:
    r, ids = await _setup(10)
    await r.xreadgroup(CONSUMER_GROUP, "c1", {STREAM: ">"}, count=10)
    await r.xack(STREAM, CONSUMER_GROUP, *ids)
    assert await j.trim_stream(r, STREAM, maxlen=4) == 6
    assert [e[0] for e in r.streams[STREAM]] == ids[6:]


async def test_trim_stream_skips_stream_without_group() -> None:
    r = FakeRedis()
    r.streams[STREAM] = [(f"{i}-0", {"data": "x"}) for i in range(1, 6)]
    r.groups[STREAM] = {}
    assert await j.trim_stream(r, STREAM, maxlen=1) == 0
    r2 = FakeRedis()
    r2.streams[STREAM] = [(f"{i}-0", {"data": "x"}) for i in range(1, 6)]
    assert await j.trim_stream(r2, STREAM, maxlen=1) == 0  # xinfo errors -> no trim


async def test_trim_streams_includes_deadletter_with_plain_maxlen() -> None:
    r, _ids = await _setup(3)
    for i in range(5):
        await r.xadd(STREAM_DEADLETTER, {"data": str(i)})
    result = await j.trim_streams(r, [STREAM], maxlen=100, deadletter_maxlen=2)
    assert result[STREAM] == 0
    assert result[STREAM_DEADLETTER] == 3
