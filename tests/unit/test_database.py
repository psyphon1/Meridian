import pytest
from packages.config.database import create_db_engine, create_session_factory, get_session
from packages.config.settings import Settings
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_DB_URL = "postgresql+psycopg://u:p@localhost:5432/meridian"


def _set_env(monkeypatch: pytest.MonkeyPatch, app_env: str | None = None) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", _DB_URL)
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)


def test_create_db_engine_returns_async_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)
    engine = create_db_engine(Settings())
    assert isinstance(engine, AsyncEngine)
    assert engine.echo is True  # default app_env is "development"


def test_create_db_engine_echo_off_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, "production")
    assert create_db_engine(Settings()).echo is False


def test_create_session_factory_returns_async_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    factory = create_session_factory(create_db_engine(Settings()))
    assert isinstance(factory, async_sessionmaker)


async def test_get_session_yields_session_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    factory = create_session_factory(create_db_engine(Settings()))
    closed: list[AsyncSession] = []
    original_close = AsyncSession.close

    async def spy_close(self: AsyncSession) -> None:
        closed.append(self)
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "close", spy_close)

    gen = get_session(factory)
    session = await anext(gen)
    assert isinstance(session, AsyncSession)
    assert closed == []  # still open while the dependency is in use

    with pytest.raises(StopAsyncIteration):
        await anext(gen)
    assert closed == [session]  # closed on dependency teardown


async def test_get_session_closes_session_when_consumer_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    factory = create_session_factory(create_db_engine(Settings()))
    closed: list[AsyncSession] = []
    original_close = AsyncSession.close

    async def spy_close(self: AsyncSession) -> None:
        closed.append(self)
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "close", spy_close)

    gen = get_session(factory)
    session = await anext(gen)
    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))
    assert closed == [session]
