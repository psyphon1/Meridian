"""Ephemeral PostgreSQL fixture — spins up a throwaway database per session."""

from collections.abc import AsyncIterator

import pytest
from packages.config.database import create_db_engine
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def pg_url() -> str:
    """Postgres URL for an ephemeral database (admin connection)."""
    import os

    host = os.environ.get("MERIDIAN_TEST_PG_HOST", "localhost")
    port = os.environ.get("MERIDIAN_TEST_PG_PORT", "5432")
    user = os.environ.get("MERIDIAN_TEST_PG_USER", "postgres")
    password = os.environ.get("MERIDIAN_TEST_PG_PASSWORD", "postgres")
    # Fast-fail connect so integration tests skip quickly when services are down.
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/postgres?connect_timeout=3"


@pytest.fixture
async def db_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Create a unique throwaway database, yield an engine, then drop it."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    admin_engine = create_async_engine(pg_url, isolation_level="AUTOCOMMIT")
    try:
        test_db_name = f"meridian_test_{__import__('uuid').uuid4().hex[:12]}"
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    except Exception as exc:
        await admin_engine.dispose()
        pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")
    await admin_engine.dispose()

    url = pg_url.rsplit("/", 1)[0] + f"/{test_db_name}"
    engine = create_db_engine(url)
    yield engine
    await engine.dispose()

    admin_engine = create_async_engine(pg_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
    await admin_engine.dispose()
