"""Janitor loop — dead-letter, reclaim stalled entries, trim streams (Task 28, spec §7.5).

A thin scheduler: all Redis logic lives in :mod:`packages.orchestration.janitor`.
"""

import asyncio

from packages.config.redis import STREAM_HIGH, STREAM_LOW, STREAM_MEDIUM
from packages.observability.logging import get_logger
from packages.orchestration.janitor import (
    DEFAULT_MAXLEN,
    DEFAULT_VISIBILITY_TIMEOUT_MS,
    dead_letter_exhausted,
    reclaim_stalled,
    trim_streams,
)
from redis.asyncio import Redis

from apps.worker.runtime import wait_or_stop

log = get_logger("worker.janitor")

STREAMS = (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW)
INTERVAL_S = 60.0


async def run_janitor_cycle(
    redis: Redis,
    consumer_name: str,
    *,
    min_idle_ms: int = DEFAULT_VISIBILITY_TIMEOUT_MS,
    maxlen: int = DEFAULT_MAXLEN,
) -> None:
    """One pass: dead-letter exhausted entries, reclaim stalled ones, trim streams.

    Stalled entries are claimed to ``consumer_name`` (this worker's consumer) so
    its backlog pass redelivers them. Dead-lettering runs first because
    ``XAUTOCLAIM`` bumps the delivery counter.
    """
    for stream in STREAMS:
        dead = await dead_letter_exhausted(redis, stream, min_idle_ms=min_idle_ms)
        claimed = await reclaim_stalled(redis, stream, consumer_name, min_idle_ms=min_idle_ms)
        if dead or claimed:
            log.info("janitor.stream", stream=stream, dead_lettered=dead, reclaimed=len(claimed))
    await trim_streams(redis, STREAMS, maxlen=maxlen, deadletter_maxlen=maxlen)


async def run_janitor(
    redis: Redis,
    consumer_name: str,
    stop: asyncio.Event,
    interval_s: float = INTERVAL_S,
) -> None:
    """Run janitor cycles every ``interval_s`` seconds until ``stop`` is set."""
    while not stop.is_set():
        try:
            await run_janitor_cycle(redis, consumer_name)
        except Exception:
            log.exception("janitor.error")
        if await wait_or_stop(stop, interval_s):
            break
    log.info("janitor.stopped")
