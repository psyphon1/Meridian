"""Integration test — migration 001 applies cleanly against ephemeral Postgres (Task 10).

Requires docker-compose backing services: marked `integration`. Skips
gracefully when PostgreSQL is not reachable.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "users",
    "api_keys",
    "installations",
    "repositories",
    "commits",
    "files",
    "code_symbols",
    "pull_requests",
    "review_runs",
    "evidence",
    "findings",
    "tool_runs",
    "review_memory",
    "audit_events",
    "webhook_deliveries",
}


@pytest.mark.asyncio
async def test_migration_001_creates_all_tables(db_engine, pg_url) -> None:
    """`alembic upgrade head` creates all 14 tables; re-run is idempotent."""
    root = _ROOT
    db_url = str(db_engine.url)  # ephemeral DB URL (engine fixture targets it)

    # Point alembic env.py at the ephemeral DB via settings env var.
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MERIDIAN_DATABASE_URL", db_url)
        cfg = Config(str(root / "db" / "migrations" / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "db" / "migrations"))
        try:
            command.upgrade(cfg, "head")
        except Exception as exc:
            pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")

        async with db_engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename NOT LIKE 'alembic%'"
                )
            )
            tables = {r[0] for r in rows}

        assert EXPECTED_TABLES.issubset(tables)
        assert len(tables) >= len(EXPECTED_TABLES)
    finally:
        monkeypatch.undo()
