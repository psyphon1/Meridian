"""Unit tests for the thin worker janitor loop (Task 28)."""

import asyncio

import pytest
from apps.worker import janitor as wj
from packages.config.redis import (
    CONSUMER_GROUP,
    STREAM_DEADLETTER,
    STREAM_HIGH,
    STREAM_LOW,
    STREAM_MEDIUM,
)
from tests.fakes import FakeRedis


async def _redis() -> FakeRedis:
    r = FakeRedis()
    for s in (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW):
        await r.xgroup_create(s, CONSUMER_GROUP, id="0", mkstream=True)
    return r


async def test_cycle_reclaims_dead_letters_and_trims() -> None:
    r = await _redis()
    stalled = await r.xadd(STREAM_MEDIUM, {"data": "stalled"})
    exhausted = await r.xadd(STREAM_HIGH, {"data": "exhausted"})
    await r.xreadgroup(CONSUMER_GROUP, "dead-worker", {STREAM_MEDIUM: ">", STREAM_HIGH: ">"})
    r.groups[STREAM_HIGH][CONSUMER_GROUP]["pending"][exhausted][2] = 3
    r.advance(10_000)
    for i in range(5):
        await r.xadd(STREAM_DEADLETTER, {"data": str(i)})

    await wj.run_janitor_cycle(r, "w1", min_idle_ms=1000, maxlen=2)  # type: ignore[arg-type]

    medium_pending = r.groups[STREAM_MEDIUM][CONSUMER_GROUP]["pending"]
    assert medium_pending[stalled][0] == "w1"  # reclaimed to the live consumer
    assert r.groups[STREAM_HIGH][CONSUMER_GROUP]["pending"] == {}  # dead-lettered + acked
    assert len(r.streams[STREAM_DEADLETTER]) == 2  # trimmed to maxlen
    assert {c["stream"] for c in r.xtrim_calls} >= {STREAM_DEADLETTER}


async def test_loop_runs_cycles_until_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = asyncio.Event()
    cycles = {"n": 0}

    async def fake_cycle(*_a: object, **_k: object) -> None:
        cycles["n"] += 1
        if cycles["n"] == 1:
            raise RuntimeError("redis blip")  # must not kill the loop
        stop.set()

    monkeypatch.setattr(wj, "run_janitor_cycle", fake_cycle)
    await asyncio.wait_for(wj.run_janitor(FakeRedis(), "w1", stop, interval_s=0.001), 5)  # type: ignore[arg-type]
    assert cycles["n"] == 2


async def test_loop_wakes_immediately_on_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = asyncio.Event()

    async def fake_cycle(*_a: object, **_k: object) -> None:
        asyncio.get_running_loop().call_later(0.01, stop.set)

    monkeypatch.setattr(wj, "run_janitor_cycle", fake_cycle)
    # 60s interval would hang if the loop used a bare sleep.
    await asyncio.wait_for(wj.run_janitor(FakeRedis(), "w1", stop, interval_s=60), 2)  # type: ignore[arg-type]
