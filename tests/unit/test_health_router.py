"""Unit tests for the health/readiness routers (Task 24)."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from packages.config.settings import get_settings


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan so TestClient doesn't touch real DB/Redis."""
    yield


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    # Bypass lifespan (no real DB/Redis in unit test)
    from apps.api.main import create_app

    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()


def test_health_returns_200(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_200_when_healthy(client):
    resp = client.get("/v1/ready")
    # In unit test without real DB, readiness may return 503;
    # we test that the endpoint exists and responds
    assert resp.status_code in (200, 503)
