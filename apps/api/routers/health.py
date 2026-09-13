"""Liveness + readiness probes (Task 24)."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns 200."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Readiness probe — checks DB + Redis connectivity."""
    try:
        from sqlalchemy import text

        engine = request.app.state.db_engine
        redis = request.app.state.redis
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await redis.ping()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}
