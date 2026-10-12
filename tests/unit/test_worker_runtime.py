"""Unit tests for worker runtime helpers (stop event + signals)."""

import asyncio
import signal
import sys
import time

import pytest
from apps.worker.runtime import install_signal_handlers, remove_signal_handlers, wait_or_stop


async def test_wait_or_stop_times_out_without_stop() -> None:
    assert await wait_or_stop(asyncio.Event(), 0.01) is False


async def test_wait_or_stop_returns_immediately_when_set() -> None:
    stop = asyncio.Event()
    stop.set()
    started = time.monotonic()
    assert await wait_or_stop(stop, 30) is True
    assert time.monotonic() - started < 1


async def test_wait_or_stop_wakes_when_set_during_wait() -> None:
    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.01, stop.set)
    started = time.monotonic()
    assert await wait_or_stop(stop, 30) is True
    assert time.monotonic() - started < 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_signals_set_the_stop_event(sig: signal.Signals) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    install_signal_handlers(loop, stop)
    try:
        signal.raise_signal(sig)
        await asyncio.wait_for(stop.wait(), 2)
    finally:
        remove_signal_handlers(loop)
    assert stop.is_set()
