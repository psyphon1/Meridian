"""Janitor loop — XAUTOCLAIM stalled entries + XTRIM stream hygiene (Task 28)."""

import asyncio

from redis.asyncio import Redis

from packages.config.redis import (
    CONSUMER_GROUP,
    STREAM_DEADLETTER,
    STREAM_HIGH,
    STREAM_LOW,
    STREAM_MEDIUM,
)
from packages.observability.logging import get_logger

log = get_logger("worker.janitor")

_STREAMS = [STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW]
_MIN_IDLE_MS = 300_000  # 5 minutes
_MAX_RETRIES = 3
_MAXLEN = 10_000


async def run_janitor(redis: Redis) -> None:
    """Every 60s: XAUTOCLAIM stalled entries, move exhausted to dead-letter, XTRIM."""
    while True:
        try:
            for stream in _STREAMS:
                claimed = await redis.xautoclaim(
                    stream, CONSUMER_GROUP, "janitor",
                    min_idle_time=_MIN_IDLE_MS,
                )
                # claimed = (next_start_id, messages, deleted_ids)
                if isinstance(claimed, tuple) and len(claimed) >= 2:
                    messages = claimed[1]
                    for entry_id, _fields in messages:
                        # Check retry count — move to dead-letter if exhausted
                        # Phase 1: simple claim, no retry tracking
                        log.info("janitor.claimed", stream=stream,
                                 entry_id=entry_id)

            for stream in _STREAMS:
                await redis.xtrim(stream, maxlen=_MAXLEN)

            await redis.xtrim(STREAM_DEADLETTER, maxlen=_MAXLEN)
        except Exception:
            log.exception("janitor.error")

        await asyncio.sleep(60)