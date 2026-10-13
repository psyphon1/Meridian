from unittest.mock import AsyncMock

from packages.security.advisory_lock import acquire_advisory_lock, compute_lock_key
from sqlalchemy.ext.asyncio import AsyncSession


def test_compute_lock_key_golden_value():
    assert compute_lock_key(repo_id=67890, pr_number=42, head_sha="abc123def456") == (
        "67890:42:abc123def456"
    )


def test_compute_lock_key_deterministic():
    assert compute_lock_key(1, 2, "sha") == compute_lock_key(1, 2, "sha")


def test_compute_lock_key_different_inputs_different_keys():
    assert compute_lock_key(1, 2, "sha") != compute_lock_key(2, 1, "sha")


def test_compute_lock_key_separator_prevents_ambiguity():
    assert compute_lock_key(1, 23, "x") != compute_lock_key(12, 3, "x")


async def test_acquire_advisory_lock_executes_hashtextextended_sql():
    session = AsyncMock(spec=AsyncSession)
    key = compute_lock_key(67890, 42, "abc123def456")

    await acquire_advisory_lock(session, key)

    session.execute.assert_awaited_once()
    statement, params = session.execute.await_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"
    assert params == {"key": "67890:42:abc123def456"}
