"""Integration fixtures that skip cleanly when a backing service is unreachable."""

import os
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture(params=[2, 3], ids=["resp2", "resp3"])
async def live_redis(request: pytest.FixtureRequest) -> AsyncIterator[Redis]:
    """Real Redis on DB 15 (flushed before/after), once per RESP protocol version."""
    host = os.environ.get("MERIDIAN_TEST_REDIS_HOST", "localhost")
    port = int(os.environ.get("MERIDIAN_TEST_REDIS_PORT", "6379"))
    client: Redis = Redis(
        host=host,
        port=port,
        db=15,
        protocol=request.param,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    try:
        await client.ping()
        await client.flushdb()
    except (RedisError, OSError) as exc:
        await client.aclose()
        pytest.skip(f"Redis not reachable for integration test: {exc}")
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def pg_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Throwaway Postgres database with all tables created (skips if PG is down)."""
    import packages.models.audit
    import packages.models.identity
    import packages.models.repository
    import packages.models.review  # noqa: F401
    from packages.models.base import Base
    from sqlalchemy import text

    name = f"meridian_test_{__import__('uuid').uuid4().hex[:12]}"
    admin = create_async_engine(pg_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:
        await admin.dispose()
        pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")
    engine = create_async_engine(pg_url.rsplit("/", 1)[0] + f"/{name}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    async with admin.begin() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    await admin.dispose()
