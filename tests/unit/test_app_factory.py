"""Unit tests for the FastAPI app factory + lifespan + deps (Task 23)."""

import pytest
from fastapi import FastAPI
from packages.config.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings_cache():
    """get_settings is lru_cached — clear between tests so each test's env wins."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_app_returns_fastapi(monkeypatch):
    from apps.api.main import create_app

    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Meridian API"
    paths = set(app.openapi()["paths"])
    assert "/v1/health" in paths
    assert "/v1/webhooks/github" in paths
