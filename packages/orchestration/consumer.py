"""Priority-ordered Redis Streams consumer loop (Task 21)."""

from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.config.redis import CONSUMER_GROUP, STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.models.schemas import JobMessage

# Priority order — high first (spec §4.3).
_PRIORITY_STREAMS = [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]


async def process_message(
    messages: dict[Any, Any],
    session_factory: async_sessionmaker[AsyncSession],
    on_job: Callable[[JobMessage], Awaitable[None]] | None = None,
) -> None:
    """Parse stream messages and invoke the job handler."""
    for _stream, entries in messages.items():
        for _msg_id, fields in entries:
            raw = fields.get("data") or fields.get(b"data")
            if isinstance(raw, bytes):
                raw = raw.decode()
            job = JobMessage.model_validate_json(raw)
            if on_job:
                await on_job(job)


async def consume_loop(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
    on_job: Callable[[JobMessage], Awaitable[None]] | None = None,
    running: Callable[[], bool] = lambda: True,
) -> None:
    """Main consumer loop — reads high → medium → low in priority order."""
    import structlog

    log = structlog.get_logger("orchestration.consumer")

    for stream in _PRIORITY_STREAMS:
        try:
            await redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:  # noqa: S110 — group already exists
            pass

    while running():
        for stream in _PRIORITY_STREAMS:
            messages = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=consumer_name,
                streams={stream: ">"},
                count=1,
                block=5000,
            )
            if messages:
                await process_message(messages, session_factory, on_job=on_job)
                break
        else:
            # All three streams empty — brief idle sleep to avoid a busy loop.
            log.debug("consumer.idle")
