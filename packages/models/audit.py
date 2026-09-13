"""Audit models — audit_events (hash-chained) and webhook_deliveries (outbox) (Task 8)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.models.base import Base, CreatedAtMixin


class AuditEvent(Base):
    """Append-only, hash-chained audit log (ADR-006).

    sequence_number is populated by a PG SEQUENCE (audit_events_seq) via
    nextval() before insert. current_hash =
    SHA256(previous_hash || event_type || actor || payload || created_at).
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sequence_number: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WebhookDelivery(Base, CreatedAtMixin):
    """Idempotency key store + transactional outbox (ADR-006).

    The webhook handler inserts a row with enqueued=false. The outbox
    publisher polls WHERE enqueued=false FOR UPDATE SKIP LOCKED, calls
    XADD, then sets enqueued=true.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    enqueued: Mapped[bool] = mapped_column(Boolean, default=False)
    enqueued_at: Mapped[datetime | None] = mapped_column(nullable=True)
