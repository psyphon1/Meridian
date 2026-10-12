"""Ingestion service — core webhook handling logic (Task 22, spec §4.1, ADR-006 D1/D2)."""

import json
from typing import Any

import structlog
from opentelemetry import trace
from pydantic import BaseModel, ValidationError
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.github.webhooks import is_event_allowed
from packages.models.audit import WebhookDelivery
from packages.models.base import ReviewStatus
from packages.models.repository import Repository
from packages.models.review import PullRequest, ReviewRun
from packages.models.schemas import (
    IngestResult,
    InstallationPayload,
    InstallationRepositoriesPayload,
    PullRequestPayload,
)
from packages.orchestration.errors import WebhookPayloadError
from packages.security.advisory_lock import acquire_advisory_lock, compute_lock_key

_log = structlog.get_logger("orchestration.ingestion")
_tracer = trace.get_tracer("meridian.orchestration.ingestion")

#: Event type → payload model (spec §4.1 step 5: "typed Pydantic model per event type").
PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "pull_request": PullRequestPayload,
    "installation": InstallationPayload,
    "installation_repositories": InstallationRepositoriesPayload,
}


def _describe(exc: ValidationError) -> str:
    """Summarise a validation error by field path + message only (never input values)."""
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
        for err in exc.errors(include_input=False, include_url=False)
    )


def _parse(event: str, delivery_id: str, raw_payload: bytes) -> tuple[dict[str, Any], BaseModel]:
    """Decode the body once and validate it against the event's schema."""
    try:
        data = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WebhookPayloadError(event, "body is not valid JSON", delivery_id) from exc
    if not isinstance(data, dict):
        raise WebhookPayloadError(event, "body must be a JSON object", delivery_id)
    try:
        model = PAYLOAD_MODELS[event].model_validate(data)
    except ValidationError as exc:
        raise WebhookPayloadError(event, _describe(exc), delivery_id) from exc
    return data, model


def _installation_id(model: InstallationPayload) -> int:
    raw = model.installation.get("id")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise WebhookPayloadError("installation", "installation.id: must be an integer")
    return raw


def _lock_key(model: BaseModel, delivery_id: str) -> int:
    """Advisory-lock key: (repo, PR, head SHA) for PRs, else (installation, delivery)."""
    if isinstance(model, PullRequestPayload):
        return compute_lock_key(
            model.repository.id, model.pull_request.number, model.pull_request.head.sha
        )
    if isinstance(model, InstallationRepositoriesPayload):
        return compute_lock_key(model.installation.id, 0, f"delivery:{delivery_id}")
    if isinstance(model, InstallationPayload):
        return compute_lock_key(_installation_id(model), 0, f"delivery:{delivery_id}")
    msg = f"unsupported payload model {type(model).__name__}"  # pragma: no cover
    raise TypeError(msg)  # pragma: no cover


def _existing_received_run(payload: PullRequestPayload) -> Select[Any]:
    """Layer-3 idempotency query: RECEIVED run for (PR, head SHA).

    Prefers ``review_runs.head_sha`` when the column exists; the current schema
    carries the SHA on ``pull_requests.head_sha`` (joined via the repository's
    GitHub id), which is equivalent for the run created for the current head.
    """
    pr = payload.pull_request
    stmt = (
        select(ReviewRun.id)
        .join(PullRequest, PullRequest.id == ReviewRun.pull_request_id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(
            Repository.github_repo_id == payload.repository.id,
            PullRequest.github_pr_number == pr.number,
            ReviewRun.status == ReviewStatus.RECEIVED,
        )
    )
    run_sha = getattr(ReviewRun, "head_sha", None)
    stmt = stmt.where((run_sha if run_sha is not None else PullRequest.head_sha) == pr.head.sha)
    return stmt.limit(1)


async def ingest_webhook(
    session: AsyncSession,
    delivery_id: str,
    event: str,
    action: str,
    raw_payload: bytes,
) -> IngestResult:
    """Core ingestion logic — runs inside the **caller's** transaction.

    Deviation from ADR-006 D1 (documented in the PR): this function does not open
    ``session.begin()`` itself; the route wraps the call in ``async with
    session.begin():`` so the advisory lock (``pg_advisory_xact_lock``) is held
    until that block commits/rolls back. Calling it outside a transaction would
    release the lock immediately after the statement.

    Steps (spec §4.1):
    0. Unsupported event/action → ``ignored`` (no DB write); malformed body →
       :class:`WebhookPayloadError` (API maps to 400 ``webhook.payload_invalid``).
    a. Advisory lock — (repo, PR, head SHA) for PR events, (installation,
       delivery) otherwise.
    b. Layer-1 idempotency: ``delivery_id`` already stored → ``replayed``.
    c. Layer-3 idempotency (PR events): existing RECEIVED review run for
       (PR, head SHA) → ``replayed`` (no new row; redelivery with a new
       delivery id).
    d. Insert ``webhook_deliveries`` outbox row (``enqueued=false``).
    e. Return ``accepted``; the caller commits.
    """
    with _tracer.start_as_current_span(
        "webhook.ingest",
        attributes={
            "meridian.delivery_id": delivery_id,
            "meridian.event": event,
            "meridian.action": action,
        },
    ) as span:
        result, reason = await _ingest(session, delivery_id, event, action, raw_payload)
        span.set_attribute("meridian.ingest.status", result.status)
        _log.info(
            "webhook.ingest",
            delivery_id=delivery_id,
            webhook_event=event,
            webhook_action=action,
            status=result.status,
            reason=reason,
        )
        return result


async def _ingest(
    session: AsyncSession,
    delivery_id: str,
    event: str,
    action: str,
    raw_payload: bytes,
) -> tuple[IngestResult, str]:
    if not is_event_allowed(event, action):
        return IngestResult(status="ignored", delivery_id=delivery_id), "event_not_allowed"

    data, model = _parse(event, delivery_id, raw_payload)

    # a. Advisory lock (released by the caller's commit/rollback)
    await acquire_advisory_lock(session, _lock_key(model, delivery_id))

    # b. Layer 1 — delivery_id
    existing = await session.execute(
        select(WebhookDelivery.id).where(WebhookDelivery.delivery_id == delivery_id)
    )
    if existing.scalar_one_or_none() is not None:
        return IngestResult(status="replayed", delivery_id=delivery_id), "delivery_id"

    # c. Layer 3 — RECEIVED run for (PR, head SHA)
    if isinstance(model, PullRequestPayload):
        dup = await session.execute(_existing_received_run(model))
        if dup.scalar_one_or_none() is not None:
            return IngestResult(status="replayed", delivery_id=delivery_id), "duplicate_pr_sha"

    # d. Outbox row (enqueued=false); reuse the already-parsed object
    session.add(
        WebhookDelivery(
            delivery_id=delivery_id,
            event=event,
            action=action,
            payload=data,
            payload_size_bytes=len(raw_payload),
            enqueued=False,
        )
    )
    # e. Accepted — caller commits
    return IngestResult(status="accepted", delivery_id=delivery_id), "persisted"
