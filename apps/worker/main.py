"""Worker main entry point — consumer loop, outbox publisher, janitor (Task 26, spec §8).

Graceful shutdown: SIGTERM/SIGINT set a shared ``asyncio.Event``; every loop
observes it, finishes its current unit of work, and returns. Tasks that do not
stop within ``DRAIN_TIMEOUT_S`` are cancelled. Exit code is 0 on a clean stop.
"""

import asyncio
import os
import socket
import sys

from packages.config.database import create_db_engine, create_session_factory
from packages.config.redis import create_redis_client
from packages.config.settings import get_settings
from packages.observability.logging import get_logger, setup_logging

from apps.worker.consumer import run_consumer_loop
from apps.worker.janitor import run_janitor
from apps.worker.outbox_publisher import run_outbox_publisher
from apps.worker.runtime import install_signal_handlers, remove_signal_handlers

DRAIN_TIMEOUT_S = 30.0


def make_consumer_name() -> str:
    """Generate a unique consumer name (hostname + PID)."""
    return f"{socket.gethostname().split('.')[0]}-{os.getpid()}"


async def _cancel_and_wait(tasks: list[asyncio.Task[None]]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def run_worker(stop: asyncio.Event | None = None) -> int:
    """Run the worker until ``stop`` is set (or a signal arrives). Returns the exit code."""
    settings = get_settings()
    setup_logging(settings)
    log = get_logger("worker.main")

    stop = stop if stop is not None else asyncio.Event()
    loop = asyncio.get_running_loop()
    install_signal_handlers(loop, stop)

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    redis = create_redis_client(settings)
    consumer_name = make_consumer_name()
    tasks: list[asyncio.Task[None]] = []
    exit_code = 0

    log.info("worker.starting", consumer=consumer_name)
    try:
        tasks = [
            asyncio.create_task(
                run_consumer_loop(redis, session_factory, consumer_name, stop), name="consumer"
            ),
            asyncio.create_task(run_outbox_publisher(redis, session_factory, stop), name="outbox"),
            asyncio.create_task(run_janitor(redis, consumer_name, stop), name="janitor"),
        ]
        stop_waiter = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait([*tasks, stop_waiter], return_when=asyncio.FIRST_COMPLETED)
        stop_waiter.cancel()
        if stop_waiter not in done:
            # A loop returned/crashed before any stop request: take the rest down.
            log.error("worker.loop_exited", loops=[t.get_name() for t in done])
            exit_code = 1
        log.info("worker.shutting_down")
        stop.set()
        _, pending = await asyncio.wait(tasks, timeout=DRAIN_TIMEOUT_S)
        if pending:
            log.warning("worker.drain_timeout", loops=[t.get_name() for t in pending])
        await _cancel_and_wait(list(pending))
        for task in tasks:
            if not task.cancelled() and (exc := task.exception()) is not None:
                log.error("worker.loop_crashed", loop=task.get_name(), error=repr(exc))
                exit_code = 1
    finally:
        await _cancel_and_wait(tasks)
        remove_signal_handlers(loop)
        await redis.aclose()
        await engine.dispose()
        log.info("worker.stopped", exit_code=exit_code)
    return exit_code


def main() -> None:
    """Console entry point."""
    sys.exit(asyncio.run(run_worker()))


if __name__ == "__main__":
    main()
