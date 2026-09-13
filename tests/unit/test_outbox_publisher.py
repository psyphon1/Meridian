"""Unit tests for the transactional outbox publisher (Task 27)."""

from packages.models.audit import WebhookDelivery

from apps.worker.outbox_publisher import build_job_message


def test_build_job_message_from_delivery():
    deliv = WebhookDelivery(
        delivery_id="d1",
        event="pull_request",
        action="opened",
        payload={
            "action": "opened",
            "installation": {"id": 12345},
            "repository": {"id": 67890, "full_name": "owner/repo"},
            "pull_request": {
                "number": 42,
                "title": "X",
                "head": {"sha": "abc"},
                "base": {"sha": "def"},
            },
        },
        payload_size_bytes=100,
        enqueued=False,
    )
    msg = build_job_message(deliv)
    assert msg.delivery_id == "d1"
    assert msg.event == "pull_request"
    assert msg.action == "opened"
    assert msg.installation_id == 12345
    assert msg.repository_id == 67890
    assert msg.repository_full_name == "owner/repo"
    assert msg.pr_number == 42
    assert msg.head_sha == "abc"
    assert msg.priority == "medium"