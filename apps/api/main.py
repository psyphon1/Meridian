"""Meridian API app factory + lifespan (Task 23)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from packages.config.database import create_db_engine, create_session_factory
from packages.config.redis import create_redis_client
from packages.config.settings import Settings, get_settings
from packages.github.client import GitHubClient
from packages.observability.logging import setup_logging

from apps.api.routers.health import router as health_router
from apps.api.routers.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage DB engine, session factory, Redis, and GitHub client lifecycle."""
    settings: Settings = app.state.settings
    setup_logging(settings)
    app.state.db_engine = create_db_engine(settings)
    app.state.session_factory = create_session_factory(app.state.db_engine)
    app.state.redis = create_redis_client(settings)
    app.state.github = GitHubClient(
        token_cache=None,
        private_key=settings.github_private_key,
        app_id=settings.github_app_id,
    )
    yield
    await app.state.db_engine.dispose()
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    """Build the Meridian FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Meridian API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health_router, prefix="/v1")
    app.include_router(webhooks_router, prefix="/v1")
    return app
