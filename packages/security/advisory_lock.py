"""PostgreSQL advisory-lock helpers for webhook ingestion (ADR-006, idempotency layer 2).

ADR-006 (Idempotency) mandates::

    pg_advisory_xact_lock(hashtextextended(repo_id || ':' || pr_number || ':' || head_sha, 0))

The Python side only builds the key string; hashing to a 64-bit lock id is done
in SQL by ``hashtextextended`` so the derivation matches the ADR exactly.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ACQUIRE_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"


def compute_lock_key(repo_id: int, pr_number: int, head_sha: str) -> str:
    """Build the deterministic lock-key string ``"{repo_id}:{pr_number}:{head_sha}"``.

    The result is passed to :func:`acquire_advisory_lock`, which hashes it in SQL
    with ``hashtextextended(key, 0)`` as specified by ADR-006.
    """
    return f"{repo_id}:{pr_number}:{head_sha}"


async def acquire_advisory_lock(session: AsyncSession, key: str) -> None:
    """Acquire a transaction-scoped advisory lock for ``key``.

    Executes ``SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))``. The
    lock is released automatically on commit or rollback of the session's
    transaction.
    """
    await session.execute(text(_ACQUIRE_LOCK_SQL), {"key": key})
