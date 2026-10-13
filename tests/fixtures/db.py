"""Ephemeral PostgreSQL fixture — creates a throwaway database per test, then drops it.

Configure with ``MERIDIAN_TEST_DATABASE_URL``: an *admin* SQLAlchemy URL for a server on
which a database may be created, e.g.
``postgresql+psycopg://<user>@localhost:5432/postgres`` (see docs/SETUP.md). No default
credentials are baked in; when the variable is unset, or the server is unreachable, the
dependent tests are skipped with an explicit reason. Any other error (bad SQL, failed
migration, assertion) is NOT swallowed.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from packages.config.database import create_db_engine_from_url
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

TEST_DB_URL_ENV = "MERIDIAN_TEST_DATABASE_URL"


@pytest.fixture
def pg_url() -> str:
    """Admin URL of the Postgres server used for ephemeral databases."""
    url = os.environ.get(TEST_DB_URL_ENV)
    if not url:
        pytest.skip(
            f"{TEST_DB_URL_ENV} is not set; export an admin Postgres URL "
            "(e.g. postgresql+psycopg://<user>@localhost:5432/postgres) to run DB integration tests"
        )
    return url


@pytest.fixture
async def db_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Create a unique throwaway database (with pgvector), yield an engine, then drop it."""
    admin_url = make_url(pg_url).update_query_dict({"connect_timeout": "3"})
    admin_engine = create_db_engine_from_url(
        admin_url.render_as_string(hide_password=False)
    ).execution_options(isolation_level="AUTOCOMMIT")
    test_db_name = f"meridian_test_{uuid.uuid4().hex[:12]}"
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    except (OperationalError, OSError) as exc:
        # Narrow skip: only "cannot reach the server" conditions.
        await admin_engine.dispose()
        pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")

    engine = create_db_engine_from_url(
        admin_url.set(database=test_db_name).render_as_string(hide_password=False)
    )
    try:
        # pgvector must be available for code_symbols.embedding (ADR-002).
        async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        yield engine
    finally:
        await engine.dispose()
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)'))
        await admin_engine.dispose()
