"""Unit tests for the webhook ingestion router + error envelope (Task 25)."""

import hashlib
import hmac
import json
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from packages.config.settings import get_settings


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan so TestClient doesn't touch real DB/Redis."""
    yield


@pytest.fixture
def app(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "k")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "testsecret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from apps.api.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    app.router.lifespan_context = _noop_lifespan

    # Stub the session factory — signature/filter tests never touch the DB,
    # but the get_db_session dependency still instantiates a session.
    class _FakeSession:
        async def __aenter__(self) -> "_FakeSession":
            return self

        async def __aexit__(self, *a: object) -> None:
            pass

    class _FakeFactory:
        def __call__(self) -> "_FakeSession":
            return _FakeSession()

    app.state.session_factory = _FakeFactory()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()


def test_error_response_structure():
    from apps.api.errors import error_response

    resp = error_response(
        "webhook",
        "webhook.signature_invalid",
        "Bad signature",
        "X-Hub-Signature-256",
        "req_123",
        401,
    )
    assert resp.status_code == 401
    body = json.loads(resp.body)
    assert body["error"]["type"] == "webhook"
    assert body["error"]["code"] == "webhook.signature_invalid"
    assert body["error"]["message"] == "Bad signature"
    assert body["error"]["param"] == "X-Hub-Signature-256"
    assert body["error"]["request_id"] == "req_123"


def test_missing_signature_returns_400(client):
    resp = client.post(
        "/v1/webhooks/github",
        content=b'{"action":"opened"}',
        headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "d1"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "webhook.signature_missing"


def test_invalid_signature_returns_401(client):
    resp = client.post(
        "/v1/webhooks/github",
        content=b'{"action":"opened"}',
        headers={
            "X-Hub-Signature-256": "sha256=bad",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "d1",
        },
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "webhook.signature_invalid"


def test_ignored_event_returns_200(client):
    body = b'{"action":"closed"}'
    sig = "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "d1",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
