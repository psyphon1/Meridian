"""FastAPI dependencies — settings + DB session (Task 23)."""

from collections.abc import AsyncIterator

from fastapi import Request
from packages.config.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession


def get_settings_dep(request: Request) -> Settings:
    """Return the app-state Settings singleton."""
    settings: Settings = request.app.state.settings
    return settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a DB session from the app-state session factory."""
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
