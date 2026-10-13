"""Unit tests for the health/readiness routers (Task 24)."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from packages.config.settings import get_settings


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """No-op lifespan so TestClient doesn't touch real DB/Redis."""
    yield


class _FakeConn:
    def __init__(self, fail: bool) -> None:
        self._fail = fail

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        if self._fail:
            raise ConnectionError("db down: postgresql://user:pw@internal-host/db")


class _FakeEngine:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    def connect(self) -> _FakeConn:
        return _FakeConn(self._fail)


class _FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.pings = 0

    async def ping(self) -> bool:
        self.pings += 1
        if self._fail:
            raise ConnectionError("redis down: redis://internal-host:6379")
        return True


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from apps.api.main import create_app

    application = create_app()
    application.router.lifespan_context = _noop_lifespan
    yield application
    get_settings.cache_clear()


def _get(app: FastAPI, path: str):  # type: ignore[no-untyped-def]
    with TestClient(app, raise_server_exceptions=False) as c:
        return c.get(path)


def test_health_returns_200(app: FastAPI) -> None:
    resp = _get(app, "/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_200_when_dependencies_healthy(app: FastAPI) -> None:
    redis = _FakeRedis()
    app.state.db_engine = _FakeEngine()
    app.state.redis = redis
    resp = _get(app, "/v1/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}
    assert redis.pings == 1


def test_ready_returns_503_when_db_fails(app: FastAPI) -> None:
    app.state.db_engine = _FakeEngine(fail=True)
    app.state.redis = _FakeRedis()
    resp = _get(app, "/v1/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "failed": ["database"]}
    assert "internal-host" not in resp.text


def test_ready_returns_503_when_redis_fails(app: FastAPI) -> None:
    app.state.db_engine = _FakeEngine()
    app.state.redis = _FakeRedis(fail=True)
    resp = _get(app, "/v1/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "failed": ["redis"]}
    assert "internal-host" not in resp.text


def test_ready_reports_all_failed_dependencies(app: FastAPI) -> None:
    app.state.db_engine = _FakeEngine(fail=True)
    app.state.redis = _FakeRedis(fail=True)
    resp = _get(app, "/v1/ready")
    assert resp.status_code == 503
    assert resp.json()["failed"] == ["database", "redis"]


def test_ready_returns_503_when_state_not_initialised(app: FastAPI) -> None:
    resp = _get(app, "/v1/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"
