"""Shared worker runtime helpers — stop-event waiting and signal handling (spec §8)."""

import asyncio
import signal
from collections.abc import Callable
from types import FrameType


async def wait_or_stop(stop: asyncio.Event, delay_s: float) -> bool:
    """Sleep up to ``delay_s`` seconds, waking immediately when ``stop`` is set.

    Returns ``True`` if the worker should stop, ``False`` if the timeout elapsed.
    """
    try:
        await asyncio.wait_for(stop.wait(), timeout=delay_s)
    except TimeoutError:
        return stop.is_set()
    return True


_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Make SIGTERM/SIGINT set ``stop`` (graceful drain instead of abrupt exit)."""
    for sig in _SIGNALS:
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows event loops
            _install_fallback(loop, stop, sig)


def _install_fallback(  # pragma: no cover - Windows only
    loop: asyncio.AbstractEventLoop, stop: asyncio.Event, sig: signal.Signals
) -> None:
    def handler(_signum: int, _frame: FrameType | None) -> None:
        loop.call_soon_threadsafe(stop.set)

    signal.signal(sig, handler)


def remove_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Undo :func:`install_signal_handlers` (best effort)."""
    remover: Callable[[signal.Signals], bool] = loop.remove_signal_handler
    for sig in _SIGNALS:
        try:
            remover(sig)
        except NotImplementedError:  # pragma: no cover - Windows event loops
            continue
