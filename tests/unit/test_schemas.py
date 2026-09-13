from packages.models.schemas import IngestResult, JobMessage, PullRequestPayload


def test_job_message_roundtrip():
    msg = JobMessage(
        delivery_id="uuid-123",
        event="pull_request",
        action="opened",
        installation_id=12345,
        repository_id=67890,
        repository_full_name="owner/repo",
        pr_number=42,
        pr_title="Add feature X",
        head_sha="abc123",
        base_sha="def789",
        priority="medium",
        traceparent="00-trace-span-01",
        enqueued_at="2026-09-13T12:00:00Z",
    )
    j = msg.model_dump_json()
    msg2 = JobMessage.model_validate_json(j)
    assert msg2.delivery_id == "uuid-123"
    assert msg2.priority == "medium"


def test_job_message_traceparent_nullable():
    msg = JobMessage(
        delivery_id="d",
        event="pull_request",
        action="opened",
        installation_id=1,
        repository_id=2,
        repository_full_name="o/r",
        pr_number=1,
        pr_title="t",
        head_sha="h",
        base_sha="b",
        priority="low",
        traceparent=None,
        enqueued_at="2026-09-13T12:00:00Z",
    )
    assert msg.traceparent is None


def test_ingest_result_accepted():
    r = IngestResult(status="accepted", delivery_id="uuid-123")
    assert r.status == "accepted"


def test_ingest_result_ignored():
    r = IngestResult(status="ignored", delivery_id="")
    assert r.status == "ignored"


def test_pull_request_payload_parses_action():
    p = PullRequestPayload.model_validate(
        {
            "action": "opened",
            "number": 42,
            "installation": {"id": 12345},
            "repository": {"id": 67890, "full_name": "owner/repo"},
            "pull_request": {
                "number": 42,
                "title": "Add X",
                "head": {"sha": "abc123"},
                "base": {"sha": "def789"},
            },
        }
    )
    assert p.action == "opened"
    assert p.installation.id == 12345
    assert p.pull_request.head.sha == "abc123"
