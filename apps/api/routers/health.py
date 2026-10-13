"""Liveness + readiness probes (Task 24)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from packages.observability.logging import get_logger
from sqlalchemy import text

router = APIRouter(tags=["health"])
log = get_logger("api.health")


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns 200."""
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse:
    """Readiness probe — 200 when DB + Redis respond, else 503 naming failed dependencies."""
    failed: list[str] = []
    try:
        async with request.app.state.db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        log.error("ready.dependency_failed", dependency="database", error_type=type(exc).__name__)
        failed.append("database")
    try:
        await request.app.state.redis.ping()
    except Exception as exc:
        log.error("ready.dependency_failed", dependency="redis", error_type=type(exc).__name__)
        failed.append("redis")
    if failed:
        return JSONResponse(status_code=503, content={"status": "not_ready", "failed": failed})
    return JSONResponse(status_code=200, content={"status": "ready"})
