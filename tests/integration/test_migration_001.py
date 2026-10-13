"""Integration tests — migration 001 against a real, ephemeral PostgreSQL database.

Requires ``MERIDIAN_TEST_DATABASE_URL`` (see tests/fixtures/db.py). The tests skip only when
that variable is unset or the server is unreachable; migration failures and assertion
failures surface normally.
"""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from packages.models.base import Base
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parents[2]

# The 15 tables migration 001 creates: 14 core tables (identity 3, repository 4, review 6,
# audit_events 1) + `webhook_deliveries` (idempotency + outbox, ADR-006).
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


def _alembic_config(engine: AsyncEngine) -> Config:
    cfg = Config(str(_ROOT / "db" / "migrations" / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "db" / "migrations"))
    # Programmatic hand-off to env.py; never mask the password (render_as_string).
    cfg.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
    return cfg


async def _upgrade(engine: AsyncEngine) -> Config:
    cfg = _alembic_config(engine)
    # env.py drives its own event loop; keep it off the test's running loop.
    await asyncio.to_thread(command.upgrade, cfg, "head")
    return cfg


async def _scalar_rows(engine: AsyncEngine, sql: str) -> list[tuple[object, ...]]:
    async with engine.connect() as conn:
        return [tuple(r) for r in await conn.execute(text(sql))]


async def test_migration_001_creates_all_tables(db_engine: AsyncEngine) -> None:
    """`alembic upgrade head` creates exactly the 15 expected tables; re-run is a no-op."""
    cfg = await _upgrade(db_engine)

    rows = await _scalar_rows(
        db_engine,
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname='public' AND tablename <> 'alembic_version'",
    )
    assert {r[0] for r in rows} == EXPECTED_TABLES
    assert len(EXPECTED_TABLES) == 15

    await asyncio.to_thread(command.upgrade, cfg, "head")  # idempotent re-run
    version = await _scalar_rows(db_engine, "SELECT version_num FROM alembic_version")
    assert version == [("001",)]


async def test_webhook_outbox_index_is_partial(db_engine: AsyncEngine) -> None:
    await _upgrade(db_engine)
    rows = await _scalar_rows(
        db_engine,
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_webhook_enqueued_false'",
    )
    assert len(rows) == 1
    indexdef = str(rows[0][0])
    assert "webhook_deliveries" in indexdef
    assert "WHERE (enqueued = false)" in indexdef


async def test_review_runs_has_head_sha_and_idempotency_index(db_engine: AsyncEngine) -> None:
    await _upgrade(db_engine)
    cols = await _scalar_rows(
        db_engine,
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name='review_runs' AND column_name='head_sha'",
    )
    assert cols == [("NO",)]
    idx = await _scalar_rows(
        db_engine,
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_review_runs_pr_head_sha'",
    )
    assert len(idx) == 1
    assert "(pull_request_id, head_sha)" in str(idx[0][0])


async def test_code_symbols_embedding_is_vector_1536(db_engine: AsyncEngine) -> None:
    await _upgrade(db_engine)
    ext = await _scalar_rows(db_engine, "SELECT extname FROM pg_extension WHERE extname='vector'")
    assert ext == [("vector",)]
    col = await _scalar_rows(
        db_engine,
        "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
        "WHERE a.attrelid = 'code_symbols'::regclass AND a.attname = 'embedding'",
    )
    assert col == [("vector(1536)",)]


async def test_orm_models_match_migrated_schema(db_engine: AsyncEngine) -> None:
    """Drift guard: autogenerate must find no difference between ORM metadata and the DB."""
    await _upgrade(db_engine)

    def _diff(sync_conn: Connection) -> list[object]:
        ctx = MigrationContext.configure(
            sync_conn, opts={"compare_type": True, "compare_server_default": False}
        )
        return list(compare_metadata(ctx, Base.metadata))

    async with db_engine.connect() as conn:
        diff = await conn.run_sync(_diff)
    assert diff == [], f"ORM models drift from migration 001: {diff}"


async def test_downgrade_base_drops_everything(db_engine: AsyncEngine) -> None:
    cfg = await _upgrade(db_engine)
    await asyncio.to_thread(command.downgrade, cfg, "base")
    rows = await _scalar_rows(
        db_engine,
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname='public' AND tablename <> 'alembic_version'",
    )
    assert rows == []
    seq = await _scalar_rows(db_engine, "SELECT 1 FROM pg_class WHERE relname = 'audit_events_seq'")
    assert seq == []
