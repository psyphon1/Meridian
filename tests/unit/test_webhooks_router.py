"""Unit tests for the webhook ingestion router + error envelope (Task 25)."""

import hashlib
import hmac
import json
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import MagicMock

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
    class _FakeTxn:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *a: object) -> None:
            return None

    class _FakeSession:
        async def __aenter__(self) -> "_FakeSession":
            return self

        async def __aexit__(self, *a: object) -> None:
            pass

        def begin(self) -> _FakeTxn:
            return _FakeTxn()

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


# --- helpers -----------------------------------------------------------------

SECRET = b"testsecret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()


def _headers(
    body: bytes, event: str = "pull_request", delivery: str | None = "d1"
) -> dict[str, str]:
    headers = {"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": event}
    if delivery is not None:
        headers["X-GitHub-Delivery"] = delivery
    return headers


def _pr_payload(action: str = "opened") -> bytes:
    return json.dumps(
        {
            "action": action,
            "number": 7,
            "installation": {"id": 1},
            "repository": {"id": 2, "full_name": "o/r"},
            "pull_request": {
                "number": 7,
                "title": "t",
                "head": {"sha": "a" * 40},
                "base": {"sha": "b" * 40},
            },
        }
    ).encode()


def _patch_ingest(monkeypatch: pytest.MonkeyPatch, result_status: str = "accepted") -> list[Any]:
    from packages.models.schemas import IngestResult

    calls: list[Any] = []

    async def fake_ingest(
        session: Any, delivery_id: str, event: str, action: str, raw: bytes
    ) -> Any:
        calls.append((delivery_id, event, action, raw))
        return IngestResult(status=result_status, delivery_id=delivery_id)

    monkeypatch.setattr("apps.api.routers.webhooks.ingest_webhook", fake_ingest)
    return calls


# --- accepted / duplicate ----------------------------------------------------


def test_valid_signature_accepted(client, monkeypatch):
    calls = _patch_ingest(monkeypatch, "accepted")
    body = _pr_payload()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 200
    assert resp.json() == {"status": "accepted", "delivery_id": "d1"}
    assert calls == [("d1", "pull_request", "opened", body)]


def test_replayed_delivery_returns_duplicate(client, monkeypatch):
    _patch_ingest(monkeypatch, "replayed")
    body = _pr_payload()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 200
    assert resp.json() == {"status": "duplicate", "delivery_id": "d1"}


# --- 500 boundary ------------------------------------------------------------


def test_unexpected_error_returns_500_envelope_without_leaking(client, monkeypatch):
    async def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("secret-payload-content")

    monkeypatch.setattr("apps.api.routers.webhooks.ingest_webhook", boom)
    logged = MagicMock()
    monkeypatch.setattr("apps.api.routers.webhooks.log", logged)
    body = _pr_payload()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 500
    err = resp.json()["error"]
    assert (err["type"], err["code"], err["request_id"]) == ("internal", "internal_error", "d1")
    assert "secret-payload-content" not in resp.text
    logged.error.assert_called_once_with(
        "webhook.internal_error", delivery_id="d1", error_type="RuntimeError"
    )
    logged.exception.assert_not_called()


# --- payload validation (400) ------------------------------------------------


def test_invalid_json_returns_400(client):
    body = b"{not json"
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"


def test_invalid_utf8_returns_400(client):
    body = b"\xff\xfe"
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"


@pytest.mark.parametrize("raw", [b"[1, 2]", b'"str"', b"42", b"null"])
def test_non_object_body_returns_400(client, raw):
    resp = client.post("/v1/webhooks/github", content=raw, headers=_headers(raw))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"


@pytest.mark.parametrize("action", [1, None, ["opened"], {"a": 1}])
def test_non_string_action_returns_400(client, action):
    body = json.dumps({"action": action}).encode()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"


def test_missing_required_object_returns_400(client, monkeypatch):
    calls = _patch_ingest(monkeypatch)
    body = json.dumps({"action": "opened", "installation": {"id": 1}}).encode()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"
    assert calls == []


def test_service_schema_validation_error_returns_400(client, monkeypatch):
    from pydantic import BaseModel, ValidationError

    class _M(BaseModel):
        x: int

    async def bad(*args: Any, **kwargs: Any) -> Any:
        try:
            _M.model_validate({"x": "nope"})
        except ValidationError:
            raise

    monkeypatch.setattr("apps.api.routers.webhooks.ingest_webhook", bad)
    body = _pr_payload()
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "webhook.payload_invalid"


def test_ping_without_action_is_ignored(client):
    body = b'{"zen": "hi"}'
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body, event="ping"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}


# --- signature edge cases ----------------------------------------------------


def test_non_ascii_signature_returns_401(client):
    body = b'{"action":"opened"}'
    headers = _headers(body)
    headers["X-Hub-Signature-256"] = "sha256=é"
    # httpx encodes header values as bytes; send latin-1 raw bytes via list of tuples
    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers=[(k.encode(), v.encode("latin-1")) for k, v in headers.items()],
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "webhook.signature_invalid"


def test_verifier_exception_is_treated_as_invalid(client, monkeypatch):
    def raising(*args: Any, **kwargs: Any) -> bool:
        raise TypeError("boom")

    monkeypatch.setattr("apps.api.routers.webhooks.verify_signature", raising)
    body = b'{"action":"opened"}'
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "webhook.signature_invalid"


# --- delivery id -------------------------------------------------------------


@pytest.mark.parametrize("delivery", [None, "", "   ", "x" * 256])
def test_missing_or_invalid_delivery_id_returns_400(client, delivery):
    body = _pr_payload()
    resp = client.post(
        "/v1/webhooks/github", content=body, headers=_headers(body, delivery=delivery)
    )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "webhook.delivery_id_missing"
    assert err["param"] == "X-GitHub-Delivery"


# --- body size cap -----------------------------------------------------------


def test_oversized_declared_body_returns_413(client, monkeypatch):
    monkeypatch.setattr("apps.api.routers.webhooks.MAX_BODY_BYTES", 10)
    body = b"x" * 11
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "webhook.payload_too_large"


def test_oversized_streamed_body_returns_413(client, monkeypatch):
    monkeypatch.setattr("apps.api.routers.webhooks.MAX_BODY_BYTES", 10)

    def gen():
        yield b"x" * 6
        yield b"x" * 6

    # generator content → chunked transfer-encoding, no Content-Length
    resp = client.post("/v1/webhooks/github", content=gen(), headers=_headers(b"x" * 12))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "webhook.payload_too_large"


# --- tracing -----------------------------------------------------------------


def test_receive_and_verify_spans_are_started(client, monkeypatch):
    names: list[str] = []

    class _Tracer:
        @contextmanager
        def start_as_current_span(self, name: str):
            names.append(name)
            yield MagicMock()

    monkeypatch.setattr("apps.api.routers.webhooks.tracer", _Tracer())
    body = b'{"action":"closed"}'
    resp = client.post("/v1/webhooks/github", content=body, headers=_headers(body))
    assert resp.status_code == 200
    assert names == ["webhook.receive", "webhook.verify"]
