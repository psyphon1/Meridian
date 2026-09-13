"""Webhook ingestion endpoint — POST /v1/webhooks/github (Task 25, spec §4.1).

Thin handler: read raw body, extract headers, verify HMAC, filter events,
delegate to the ingest_webhook service. No business logic here.
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from packages.config.settings import Settings
from packages.github.webhooks import is_event_allowed
from packages.observability.logging import get_logger
from packages.orchestration.ingestion import ingest_webhook
from packages.security.hmac_verify import verify_signature
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, get_settings_dep
from apps.api.errors import error_response

router = APIRouter(tags=["webhooks"])
log = get_logger("api.webhooks")


@router.post("/webhooks/github")
async def receive_github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008 — FastAPI DI pattern
) -> JSONResponse:
    """Webhook ingestion endpoint (spec §4.1, 10-second critical path)."""
    settings: Settings = get_settings_dep(request)
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    # 1. Read raw body
    raw_body = await request.body()

    # 2. Extract headers
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")

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

    # 4. Verify HMAC → fail → 401
    if not verify_signature(raw_body, signature, settings.github_webhook_secret):
        log.warning("webhook.signature_invalid", delivery_id=delivery_id)
        return error_response(
            "webhook",
            "webhook.signature_invalid",
            "Webhook signature verification failed.",
            "X-Hub-Signature-256",
            delivery_id,
            401,
        )

    # 5. Parse JSON to extract action
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return error_response(
            "webhook",
            "webhook.payload_invalid",
            "Invalid JSON payload.",
            None,
            delivery_id,
            400,
        )
    action = body.get("action", "")

    # 6. Event/action filter → no match → 200 ignored
    if not is_event_allowed(event or "", action):
        return JSONResponse(status_code=200, content={"status": "ignored"})

    # 7. Delegate to service
    try:
        async with session.begin():
            result = await ingest_webhook(
                session,
                delivery_id,
                event or "",
                action,
                raw_body,
            )
        # 8. Map IngestResult → 200
        if result.status == "accepted":
            return JSONResponse(
                status_code=200,
                content={"status": "accepted", "delivery_id": result.delivery_id},
            )
        return JSONResponse(
            status_code=200,
            content={"status": "duplicate", "delivery_id": result.delivery_id},
        )
    except Exception:
        log.exception("webhook.internal_error", delivery_id=delivery_id)
        return error_response(
            "internal",
            "internal_error",
            "An unexpected error occurred.",
            None,
            delivery_id,
            500,
        )
