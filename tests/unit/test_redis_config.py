from redis.asyncio import Redis


def test_create_redis_client_returns_redis(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from packages.config.redis import create_redis_client
    from packages.config.settings import Settings

    client = create_redis_client(Settings())
    assert isinstance(client, Redis)


def test_stream_constants_defined():
    from packages.config.redis import (
        CONSUMER_GROUP,
        STREAM_DEADLETTER,
        STREAM_HIGH,
        STREAM_LOW,
        STREAM_MEDIUM,
    )

    assert STREAM_HIGH == "meridian:reviews:high"
    assert STREAM_MEDIUM == "meridian:reviews:medium"
    assert STREAM_LOW == "meridian:reviews:low"
    assert STREAM_DEADLETTER == "meridian:reviews:deadletter"
    assert CONSUMER_GROUP == "meridian-workers"
