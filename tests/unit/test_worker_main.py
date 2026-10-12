"""Unit tests for the worker main entry point (Task 26): naming + graceful shutdown."""

import asyncio
import os
import re
import signal
import sys
from typing import Any

import pytest
from apps.worker import main as wm
from tests.fakes import eventually


def test_consumer_name_is_hostname_dash_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wm.socket, "gethostname", lambda: "host-1.example.com")
    assert wm.make_consumer_name() == f"host-1-{os.getpid()}"
    assert re.fullmatch(r"[^.]+-\d+", wm.make_consumer_name())


class _Engine:
    disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _Redis:
    closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"engine": _Engine(), "redis": _Redis(), "started": []}
    monkeypatch.setattr(wm, "get_settings", lambda: object())
    monkeypatch.setattr(wm, "setup_logging", lambda _s: None)
    monkeypatch.setattr(wm, "create_db_engine", lambda _s: state["engine"])
    monkeypatch.setattr(wm, "create_session_factory", lambda _e: object())
    monkeypatch.setattr(wm, "create_redis_client", lambda _s: state["redis"])
    return state


def _well_behaved(state: dict[str, Any], name: str) -> Any:
    async def loop(*args: Any) -> None:
        stop = next(a for a in args if isinstance(a, asyncio.Event))
        state["started"].append(name)
        await stop.wait()
        state.setdefault("stopped", []).append(name)

    return loop


def _patch_loops(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any]) -> None:
    monkeypatch.setattr(wm, "run_consumer_loop", _well_behaved(state, "consumer"))
    monkeypatch.setattr(wm, "run_outbox_publisher", _well_behaved(state, "outbox"))
    monkeypatch.setattr(wm, "run_janitor", _well_behaved(state, "janitor"))


async def test_stop_event_ends_all_loops_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, patched: dict[str, Any]
) -> None:
    _patch_loops(monkeypatch, patched)
    stop = asyncio.Event()
    task = asyncio.create_task(wm.run_worker(stop))
    await eventually(lambda: len(patched["started"]) == 3)
    assert not task.done()
    stop.set()
    assert await asyncio.wait_for(task, 5) == 0
    assert sorted(patched["stopped"]) == ["consumer", "janitor", "outbox"]
    assert patched["engine"].disposed and patched["redis"].closed


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_signal_triggers_graceful_shutdown(
    monkeypatch: pytest.MonkeyPatch, patched: dict[str, Any], sig: signal.Signals
) -> None:
    _patch_loops(monkeypatch, patched)
    task = asyncio.create_task(wm.run_worker())
    await eventually(lambda: len(patched["started"]) == 3)
    signal.raise_signal(sig)
    assert await asyncio.wait_for(task, 5) == 0
    assert sorted(patched["stopped"]) == ["consumer", "janitor", "outbox"]
    # Handlers were removed again: default SIGINT behaviour is restored.
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


async def test_loop_that_exits_early_takes_the_worker_down_with_exit_1(
    monkeypatch: pytest.MonkeyPatch, patched: dict[str, Any]
) -> None:
    _patch_loops(monkeypatch, patched)

    async def crashes(*_args: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(wm, "run_outbox_publisher", crashes)
    assert await asyncio.wait_for(wm.run_worker(), 5) == 1
    assert sorted(patched["stopped"]) == ["consumer", "janitor"]  # others drained cleanly


async def test_stuck_loop_is_cancelled_after_drain_timeout(
    monkeypatch: pytest.MonkeyPatch, patched: dict[str, Any]
) -> None:
    _patch_loops(monkeypatch, patched)

    async def stuck(*_args: Any) -> None:
        patched["started"].append("stuck")
        await asyncio.sleep(3600)  # ignores stop

    monkeypatch.setattr(wm, "run_janitor", stuck)
    monkeypatch.setattr(wm, "DRAIN_TIMEOUT_S", 0.05)
    stop = asyncio.Event()
    task = asyncio.create_task(wm.run_worker(stop))
    await eventually(lambda: len(patched["started"]) == 3)
    stop.set()
    assert await asyncio.wait_for(task, 5) == 0
    assert patched["engine"].disposed


def test_main_exits_with_run_worker_code(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_worker() -> int:
        return 0

    monkeypatch.setattr(wm, "run_worker", fake_run_worker)
    with pytest.raises(SystemExit) as exc:
        wm.main()
    assert exc.value.code == 0
