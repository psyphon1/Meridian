"""Unit tests for the Redis Streams producer (Task 20)."""

import pytest

from packages.models.schemas import JobMessage


def _make_job(**overrides: object) -> JobMessage:
    defaults: dict[str, object] = {
        "delivery_id": "d1",
        "event": "pull_request",
        "action": "opened",
        "installation_id": 1,
        "repository_id": 2,
        "repository_full_name": "o/r",
        "pr_number": 1,
        "pr_title": "t",
        "head_sha": "h",
        "base_sha": "b",
        "priority": "medium",
        "traceparent": None,
        "enqueued_at": "2026-09-13T12:00:00Z",
    }
    defaults.update(overrides)
    return JobMessage(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_enqueue_job_adds_to_priority_stream():
    from packages.orchestration.producer import enqueue_job

    class FakeRedis:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str]]] = []

        async def xadd(self, stream: str, fields: dict[str, str]) -> str:
            self.calls.append((stream, fields))
            return "1234-0"

    fake = FakeRedis()
    msg_id = await enqueue_job(fake, "medium", _make_job())  # type: ignore[arg-type]
    assert msg_id == "1234-0"
    stream, fields = fake.calls[0]
    assert stream == "meridian:reviews:medium"
    assert "d1" in fields["data"]


@pytest.mark.asyncio
async def test_enqueue_job_routes_by_priority():
    from packages.orchestration.producer import enqueue_job

    streams: list[str] = []

    class FakeRedis:
        async def xadd(self, stream: str, fields: dict[str, str]) -> str:
            streams.append(stream)
            return "1-0"

    await enqueue_job(FakeRedis(), "high", _make_job(priority="high"))  # type: ignore[arg-type]
    await enqueue_job(FakeRedis(), "low", _make_job(priority="low"))  # type: ignore[arg-type]
    assert streams == ["meridian:reviews:high", "meridian:reviews:low"]