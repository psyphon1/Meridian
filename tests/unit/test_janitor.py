"""Unit tests for the janitor loop (Task 28)."""

import contextlib

import pytest
from apps.worker.janitor import run_janitor


@pytest.mark.asyncio
async def test_janitor_runs_one_cycle(monkeypatch):
    """Janitor should call xautoclaim + xtrim + xack without error."""
    calls = []

    class FakeRedis:
        async def xautoclaim(self, stream, group, consumer, min_idle_time):
            calls.append(("xautoclaim", stream))
            return [], [], []

        async def xadd(self, stream, fields):
            calls.append(("xadd", stream))
            return "1-0"

        async def xack(self, stream, group, eid):
            calls.append(("xack", stream))

        async def xtrim(self, stream, maxlen):
            calls.append(("xtrim", stream))

    # Run one cycle by monkeypatching the sleep + loop flag
    iterations = {"n": 0}

    async def fake_sleep(seconds):
        iterations["n"] += 1
        if iterations["n"] >= 1:
            raise SystemExit

    monkeypatch.setattr("apps.worker.janitor.asyncio.sleep", fake_sleep)
    with contextlib.suppress(SystemExit):
        await run_janitor(FakeRedis())

    assert any(c[0] == "xautoclaim" for c in calls)
    assert any(c[0] == "xtrim" for c in calls)
