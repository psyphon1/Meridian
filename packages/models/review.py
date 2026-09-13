"""Review-domain models — PRs, runs, findings, evidence, tool runs, memory (Task 7)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.models.base import (
    Base,
    CreatedAtMixin,
    FindingSeverity,
    PRState,
    ReviewStatus,
    RiskTier,
    TimestampMixin,
)


class PullRequest(Base, TimestampMixin):
    """A pull request seen by Meridian."""

    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_number", name="uq_pr_repo_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False
    )
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=PRState.OPEN)


class ReviewRun(Base, TimestampMixin):
    """One execution of the review pipeline for a PR head SHA."""

    __tablename__ = "review_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ReviewStatus.RECEIVED)
    risk_tier: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default=RiskTier.MEDIUM
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Evidence(Base, CreatedAtMixin):
    """Evidence artifact backing a finding (evidence gate, ADR-004)."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_ref: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Finding(Base, CreatedAtMixin):
    """A review finding tied to a review run."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False, default=FindingSeverity.MEDIUM
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("evidence.id"), nullable=True
    )


class ToolRun(Base, CreatedAtMixin):
    """Record of a single tool execution inside a review run."""

    __tablename__ = "tool_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_runs.id"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReviewMemory(Base, TimestampMixin):
    """Per-repository durable memory (JSONB)."""

    __tablename__ = "review_memory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
