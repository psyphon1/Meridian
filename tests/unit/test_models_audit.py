from packages.models.audit import AuditEvent, WebhookDelivery
from sqlalchemy import inspect as sa_inspect


def test_audit_event_columns():
    cols = {c.name for c in sa_inspect(AuditEvent).columns}
    assert cols == {
        "id",
        "sequence_number",
        "previous_hash",
        "current_hash",
        "event_type",
        "actor",
        "ip",
        "payload",
        "created_at",
    }


def test_audit_sequence_number_unique():
    assert sa_inspect(AuditEvent).columns["sequence_number"].unique is True


def test_webhook_delivery_columns():
    cols = {c.name for c in sa_inspect(WebhookDelivery).columns}
    assert cols == {
        "id",
        "delivery_id",
        "event",
        "action",
        "payload",
        "payload_size_bytes",
        "processed",
        "processed_at",
        "enqueued",
        "enqueued_at",
        "created_at",
    }


def test_webhook_delivery_id_unique():
    assert sa_inspect(WebhookDelivery).columns["delivery_id"].unique is True
