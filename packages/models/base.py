"""Declarative base, timestamp mixins, and domain enum constants (Task 4)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all Meridian models."""


class TimestampMixin:
    """Adds created_at and updated_at columns with server defaults."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreatedAtMixin:
    """Adds only created_at (for append-only tables)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewStatus(StrEnum):
    """Lifecycle of a review run (spec §5)."""

    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskTier(StrEnum):
    """Risk tier assigned to a review run."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingSeverity(StrEnum):
    """Severity levels for findings (evidence gate, ADR-004)."""

    BLOCKING = "BLOCKING"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NIT = "NIT"


class InstallationStatus(StrEnum):
    """GitHub App installation lifecycle."""

    ACTIVE = "active"
    UNINSTALLED = "uninstalled"


class PRState(StrEnum):
    """Pull request state as reported by GitHub."""

    OPEN = "open"
    CLOSED = "closed"
