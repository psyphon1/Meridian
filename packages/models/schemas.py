"""Pydantic schemas — JobMessage, IngestResult, webhook payload models (Task 9)."""

from dataclasses import dataclass

from pydantic import BaseModel, Field


class JobMessage(BaseModel):
    """Reference message placed on Redis Streams (spec §4.3).

    The worker reads the full payload from webhook_deliveries by delivery_id.
    """

    delivery_id: str
    event: str
    action: str
    installation_id: int
    repository_id: int
    repository_full_name: str
    pr_number: int
    pr_title: str
    head_sha: str
    base_sha: str
    priority: str = "medium"
    traceparent: str | None = None
    enqueued_at: str


class IngestResult(BaseModel):
    """Result of the ingest_webhook service call."""

    status: str  # "accepted" | "ignored" | "replayed"
    delivery_id: str = ""


@dataclass(frozen=True)
class WebhookHeaders:
    """Extracted webhook headers from the raw request."""

    signature: str | None
    event: str | None
    delivery_id: str | None


# --- Webhook payload models ---


class _InstallationRef(BaseModel):
    id: int


class _RepositoryRef(BaseModel):
    id: int
    full_name: str


class _ShaRef(BaseModel):
    sha: str


class _PullRequestRef(BaseModel):
    number: int
    title: str
    head: _ShaRef
    base: _ShaRef


class PullRequestPayload(BaseModel):
    action: str
    number: int
    installation: _InstallationRef
    repository: _RepositoryRef
    pull_request: _PullRequestRef


class InstallationPayload(BaseModel):
    action: str
    installation: dict[str, object]  # full installation object — shape varies


class InstallationRepositoriesPayload(BaseModel):
    action: str
    installation: _InstallationRef
    repositories_added: list[_RepositoryRef] = Field(default_factory=list)
    repositories_removed: list[_RepositoryRef] = Field(default_factory=list)
