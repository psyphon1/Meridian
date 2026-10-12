"""Webhook ingestion endpoint — POST /v1/webhooks/github (Task 25, spec §4.1).

Thin handler: read the raw body (size-capped), extract headers, verify HMAC,
filter events, shape-check the payload, and delegate to the ingest_webhook
service. No business logic here.

Transaction note (deviation from spec §4.1): the route owns the transaction
boundary (``async with session.begin()``) rather than the service. The service
still runs entirely inside the caller's transaction, so the outbox row and the
advisory lock commit/release atomically.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from packages.config.settings import Settings
from packages.github.webhooks import is_event_allowed
from packages.observability.logging import get_logger
from packages.orchestration.ingestion import ingest_webhook
from packages.security.hmac_verify import verify_signature
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, get_settings_dep
from apps.api.errors import error_response

router = APIRouter(tags=["webhooks"])
log = get_logger("api.webhooks")
tracer = trace.get_tracer("meridian.api.webhooks")

# GitHub's documented maximum webhook payload size is 25 MB.
MAX_BODY_BYTES = 25 * 1024 * 1024
# webhook_deliveries.delivery_id is VARCHAR(255).
MAX_DELIVERY_ID_LEN = 255

# Required top-level object keys per event (shape check only — no business logic).
_REQUIRED_OBJECT_KEYS: dict[str, tuple[str, ...]] = {
    "pull_request": ("installation", "repository", "pull_request"),
    "installation": ("installation",),
    "installation_repositories": ("installation",),
}


async def _read_body_capped(request: Request, limit: int) -> bytes | None:
    """Read the request body, returning None as soon as it exceeds ``limit`` bytes."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        return None
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _signature_is_valid(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verify the signature; any failure to compare counts as invalid (never raises)."""
    try:
        return verify_signature(raw_body, signature, secret)
    except (TypeError, ValueError):  # e.g. non-ASCII header text in compare_digest
        return False


def _payload_invalid(delivery_id: str, message: str) -> JSONResponse:
    log.warning("webhook.payload_invalid", delivery_id=delivery_id)
    return error_response("webhook", "webhook.payload_invalid", message, None, delivery_id, 400)


def _shape_problem(event: str, body: dict[str, Any]) -> str | None:
    """Return a message when required top-level objects are absent, else None."""
    for key in _REQUIRED_OBJECT_KEYS.get(event, ()):
        if not isinstance(body.get(key), dict):
            return f"Payload is missing required object '{key}'."
    return None


@router.post("/webhooks/github")
async def receive_github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008 — FastAPI DI pattern
) -> JSONResponse:
    """Webhook ingestion endpoint (spec §4.1, 10-second critical path)."""
    raw_delivery = request.headers.get("X-GitHub-Delivery", "").strip()
    delivery_id = raw_delivery or "unknown"
    with tracer.start_as_current_span("webhook.receive") as span:
        span.set_attribute("delivery_id", delivery_id)
        try:
            return await _handle(request, session, raw_delivery)
        except Exception as exc:
            # Deliberately log only the exception type + delivery_id: exception
            # text/tracebacks may embed payload content (untrusted, may be sensitive).
            log.error(
                "webhook.internal_error", delivery_id=delivery_id, error_type=type(exc).__name__
            )
            return error_response(
                "internal",
                "internal_error",
                "An unexpected error occurred.",
                None,
                delivery_id,
                500,
            )


async def _handle(request: Request, session: AsyncSession, raw_delivery: str) -> JSONResponse:
    """Run the ingestion flow; unexpected exceptions propagate to the 500 boundary."""
    settings: Settings = get_settings_dep(request)
    delivery_id = raw_delivery or "unknown"

    # 1. Delivery id is required (used for idempotency + correlation)
    if not raw_delivery or len(raw_delivery) > MAX_DELIVERY_ID_LEN:
        log.warning("webhook.delivery_id_missing")
        return error_response(
            "webhook",
            "webhook.delivery_id_missing",
            "X-GitHub-Delivery header is required (1-255 characters).",
            "X-GitHub-Delivery",
            delivery_id[:64],
            400,
        )

    # 2. Read raw body with a hard size cap
    raw_body = await _read_body_capped(request, MAX_BODY_BYTES)
    if raw_body is None:
        log.warning("webhook.payload_too_large", delivery_id=delivery_id)
        return error_response(
            "webhook",
            "webhook.payload_too_large",
            f"Payload exceeds the {MAX_BODY_BYTES} byte limit.",
            None,
            delivery_id,
            413,
        )

    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event") or ""

    # 3. Missing signature → 400
    if not signature:
        log.warning("webhook.signature_missing", delivery_id=delivery_id)
        return error_response(
            "webhook",
            "webhook.signature_missing",
            "X-Hub-Signature-256 header is required.",
            "X-Hub-Signature-256",
            delivery_id,
            400,
        )

    # 4. Verify HMAC → fail (including malformed/non-ASCII header) → 401
    with tracer.start_as_current_span("webhook.verify"):
        valid = _signature_is_valid(raw_body, signature, settings.github_webhook_secret)
    if not valid:
        log.warning("webhook.signature_invalid", delivery_id=delivery_id)
        return error_response(
            "webhook",
            "webhook.signature_invalid",
            "Webhook signature verification failed.",
            "X-Hub-Signature-256",
            delivery_id,
            401,
        )

    # 5. Parse JSON; body must be an object
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        return _payload_invalid(delivery_id, "Invalid JSON payload.")
    if not isinstance(body, dict):
        return _payload_invalid(delivery_id, "Payload must be a JSON object.")
    action = body.get("action", "")
    if not isinstance(action, str):
        return _payload_invalid(delivery_id, "Payload field 'action' must be a string.")

    # 6. Event/action filter → no match → 200 ignored
    if not is_event_allowed(event, action):
        log.info("webhook.ignored", delivery_id=delivery_id, github_event=event, action=action[:64])
        return JSONResponse(status_code=200, content={"status": "ignored"})

    # 7. Shape check of required top-level objects
    problem = _shape_problem(event, body)
    if problem is not None:
        return _payload_invalid(delivery_id, problem)

    # 8. Delegate to service (route owns the transaction — see module docstring)
    try:
        async with session.begin():
            result = await ingest_webhook(session, delivery_id, event, action, raw_body)
    except ValidationError:
        return _payload_invalid(delivery_id, "Payload failed schema validation.")

    # 9. Map IngestResult → 200
    if result.status == "accepted":
        log.info("webhook.accepted", delivery_id=result.delivery_id, github_event=event)
        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "delivery_id": result.delivery_id},
        )
    log.info("webhook.duplicate", delivery_id=result.delivery_id, github_event=event)
    return JSONResponse(
        status_code=200,
        content={"status": "duplicate", "delivery_id": result.delivery_id},
    )
