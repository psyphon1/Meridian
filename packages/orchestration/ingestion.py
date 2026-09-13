"""Ingestion service — core webhook handling logic (Task 22, spec §4.1)."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.models.audit import WebhookDelivery
from packages.models.schemas import IngestResult, PullRequestPayload
from packages.security.advisory_lock import acquire_advisory_lock, compute_lock_key


async def ingest_webhook(
    session: AsyncSession,
    delivery_id: str,
    event: str,
    action: str,
    raw_payload: bytes,
) -> IngestResult:
    """Core ingestion logic — runs inside caller's transaction.

    Steps (spec §4.1):
    a. Acquire advisory lock on (repo_id, pr_number, head_sha)
    b. Idempotency check 1: delivery_id in webhook_deliveries → replayed
    c. Idempotency check 2: existing RECEIVED run on (pr, head_sha)
       (Phase 1: skipped — delivery_id check is sufficient)
    d. Insert webhook_delivery row with enqueued=false
    e. Return IngestResult(status="accepted")

    Caller commits the transaction (releasing the advisory lock).
    """
    payload = PullRequestPayload.model_validate_json(raw_payload)
    pr = payload.pull_request

    # a. Advisory lock
    lock_key = compute_lock_key(
        payload.repository.id,
        pr.number,
        pr.head.sha,
    )
    await acquire_advisory_lock(session, lock_key)

    # b. Idempotency check 1 — delivery_id
    existing = await session.execute(
        select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    )
    if existing.scalar_one_or_none() is not None:
        return IngestResult(status="replayed", delivery_id=delivery_id)

    # c. Idempotency check 2 — (Phase 2: query review_runs for
    #    existing RECEIVED run on (pull_request_id, head_sha))
    #    Phase 1: delivery_id check is sufficient.

    # d. Insert webhook_delivery (outbox row, enqueued=false)
    delivery = WebhookDelivery(
        delivery_id=delivery_id,
        event=event,
        action=action,
        payload=json.loads(raw_payload),
        payload_size_bytes=len(raw_payload),
        enqueued=False,
    )
    session.add(delivery)

    # e. Return accepted — caller commits
    return IngestResult(status="accepted", delivery_id=delivery_id)
