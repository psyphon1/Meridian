"""Unit tests for the Redis Streams consumer (Task 21)."""

import pytest

from packages.models.schemas import JobMessage


def _record(processed: list[JobMessage]):
    async def handler(job: JobMessage) -> None:
        processed.append(job)

    return handler


@pytest.mark.asyncio
async def test_process_message_parses_job():
    from packages.orchestration.consumer import process_message

    job = JobMessage(
        delivery_id="d1",
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
    raw = {
        b"meridian:reviews:low": [
            (b"1-0", {b"data": job.model_dump_json().encode()}),
        ],
    }
    processed = []

    class FakeFactory:
        async def __call__(self) -> object:
            class S:
                async def __aenter__(self) -> "S":
                    return self

                async def __aexit__(self, *a: object) -> None:
                    pass

                async def execute(self, *a: object, **kw: object) -> None:
                    pass

                async def commit(self) -> None:
                    pass

            return S()

    await process_message(
        raw,  # type: ignore[arg-type]
        FakeFactory(),  # type: ignore[arg-type]
        on_job=_record(processed),
    )
    assert len(processed) == 1
    assert processed[0].delivery_id == "d1"


@pytest.mark.asyncio
async def test_process_message_invalid_json_raises():
    """Malformed payloads propagate — the janitor/dead-letter path handles
    them in Phase 2 (process_message does not swallow validation errors)."""
    import pydantic

    from packages.orchestration.consumer import process_message

    raw: dict[bytes, list[tuple[bytes, dict[bytes, bytes]]]] = {
        b"meridian:reviews:high": [(b"1-0", {b"data": b"{}"})],
    }

    class FakeFactory:
        async def __call__(self) -> object:
            return None

    with pytest.raises(pydantic.ValidationError):
        await process_message(raw, FakeFactory())  # type: ignore[arg-type]