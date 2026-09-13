"""Ephemeral Redis fixture — flushes a test DB per session."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from redis.asyncio import Redis


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """Yield a Redis client pointed at DB 15 (test DB), flushed before/after."""
    import os

    host = os.environ.get("MERIDIAN_TEST_REDIS_HOST", "localhost")
    port = int(os.environ.get("MERIDIAN_TEST_REDIS_PORT", "6379"))
    client: Redis[Any] = Redis(host=host, port=port, db=15, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
