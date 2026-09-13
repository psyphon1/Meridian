"""Worker main entry point — runs consumer loop, outbox publisher, janitor (Task 26)."""

import asyncio
import os
import signal
import socket

from apps.worker.consumer import run_consumer_loop
from apps.worker.janitor import run_janitor
from apps.worker.outbox_publisher import run_outbox_publisher
from packages.config.database import create_db_engine, create_session_factory
from packages.config.redis import create_redis_client
from packages.config.settings import get_settings
from packages.observability.logging import get_logger, setup_logging


def make_consumer_name() -> str:
    """Generate a unique consumer name (hostname + PID)."""
    return f"{socket.gethostname().split('.')[0]}-{os.getpid()}"


_running = True


def _signal_handler(sig: object, frame: object) -> None:
    global _running
    _running = False


async def run_worker() -> None:
    """Main worker entry point."""
    global _running

    settings = get_settings()
    setup_logging(settings)
    log = get_logger("worker.main")

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    redis = create_redis_client(settings)
    consumer_name = make_consumer_name()

    signal.signal(signal.SIGTERM, _signal_handler)

    log.info("worker.starting", consumer=consumer_name)

    tasks = [
        asyncio.create_task(
            run_consumer_loop(redis, session_factory, consumer_name)
        ),
        asyncio.create_task(run_outbox_publisher(redis, session_factory)),
        asyncio.create_task(run_janitor(redis)),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("worker.shutting_down")
    finally:
        await redis.aclose()
        await engine.dispose()
        _running = False
        log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())