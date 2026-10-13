from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.config.settings import Settings


def create_db_engine_from_url(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine from an explicit URL (tools, migrations, tests)."""
    return create_async_engine(url, echo=echo, pool_pre_ping=True)


def create_db_engine(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings."""
    return create_db_engine_from_url(
        settings.database_url,
        echo=(settings.app_env == "development"),
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async_sessionmaker bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a DB session."""
    async with session_factory() as session:
        yield session
