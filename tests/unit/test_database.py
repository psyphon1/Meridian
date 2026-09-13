from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker


def test_create_db_engine_returns_async_engine(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.database import create_db_engine
    from packages.config.settings import Settings

    engine = create_db_engine(Settings())
    assert isinstance(engine, AsyncEngine)


def test_create_session_factory_returns_async_sessionmaker(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.database import create_db_engine, create_session_factory
    from packages.config.settings import Settings

    engine = create_db_engine(Settings())
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)
