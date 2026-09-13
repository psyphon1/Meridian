import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def compute_lock_key(repo_id: int, pr_number: int, head_sha: str) -> int:
    """Compute a 64-bit advisory lock key from repo_id, pr_number, head_sha.

    Uses a SHA-256 digest of the composite key, truncated to a signed 64-bit
    int. Deterministic; collisions are astronomically rare (ADR-006).
    """
    raw = f"{repo_id}:{pr_number}:{head_sha}"
    h = hashlib.sha256(raw.encode()).digest()
    return int.from_bytes(h[:8], byteorder="big", signed=True)


async def acquire_advisory_lock(session: AsyncSession, key: int) -> None:
    """Acquire a transaction-scoped PostgreSQL advisory lock.

    Uses pg_advisory_xact_lock — released on commit/rollback.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": key},
    )
