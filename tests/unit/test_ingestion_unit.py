"""ingest_webhook paths that never touch the database (ignore / invalid payload)."""

import json

import pytest
from packages.models.schemas import IngestResult
from packages.orchestration.errors import (
    WEBHOOK_PAYLOAD_INVALID,
    OrchestrationError,
    WebhookPayloadError,
)
from packages.orchestration.ingestion import ingest_webhook


class NoDBSession:
    """Fails the test if ingestion reaches the database."""

    async def execute(self, *a: object, **kw: object) -> None:
        pytest.fail("DB must not be touched")

    def add(self, *a: object) -> None:
        pytest.fail("DB must not be touched")


async def test_unsupported_event_is_ignored_without_db():
    r = await ingest_webhook(NoDBSession(), "d1", "push", "created", b"{}")  # type: ignore[arg-type]
    assert r == IngestResult(status="ignored", delivery_id="d1")


async def test_unsupported_action_is_ignored_without_db():
    r = await ingest_webhook(NoDBSession(), "d1", "pull_request", "closed", b"{}")  # type: ignore[arg-type]
    assert r.status == "ignored"


@pytest.mark.parametrize("event", ["pull_request", "installation", "installation_repositories"])
@pytest.mark.parametrize("body", [b"not json", b"\xff\xfe", b"[]", b"42", b"{}"])
async def test_invalid_payload_raises_typed_error(event, body):
    action = {"pull_request": "opened", "installation": "created"}.get(event, "added")
    with pytest.raises(WebhookPayloadError) as ei:
        await ingest_webhook(NoDBSession(), "d9", event, action, body)  # type: ignore[arg-type]
    err = ei.value
    assert isinstance(err, OrchestrationError)
    assert err.code == WEBHOOK_PAYLOAD_INVALID == "webhook.payload_invalid"
    assert err.event == event
    assert err.delivery_id == "d9"


async def test_validation_detail_names_field_but_not_values():
    body = json.dumps({"action": "opened", "number": "SECRET-VALUE"}).encode()
    with pytest.raises(WebhookPayloadError) as ei:
        await ingest_webhook(NoDBSession(), "d", "pull_request", "opened", body)  # type: ignore[arg-type]
    assert "SECRET-VALUE" not in ei.value.detail
    assert "number" in ei.value.detail


async def test_installation_payload_requires_integer_id():
    body = json.dumps({"action": "created", "installation": {"id": "abc"}}).encode()
    with pytest.raises(WebhookPayloadError, match=r"installation\.id"):
        await ingest_webhook(NoDBSession(), "d", "installation", "created", body)  # type: ignore[arg-type]
