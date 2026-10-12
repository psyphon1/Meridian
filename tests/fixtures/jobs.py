"""Shared job-message helpers for consumer tests."""

from packages.models.schemas import JobMessage


def make_job(delivery_id: str = "d1", **overrides: object) -> JobMessage:
    data: dict[str, object] = {
        "delivery_id": delivery_id,
        "event": "pull_request",
        "action": "opened",
        "installation_id": 1,
        "repository_id": 2,
        "repository_full_name": "o/r",
        "pr_number": 1,
        "pr_title": "t",
        "head_sha": "h",
        "base_sha": "b",
        "priority": "low",
        "traceparent": None,
        "enqueued_at": "2026-09-13T12:00:00Z",
    }
    data.update(overrides)
    return JobMessage(**data)  # type: ignore[arg-type]


class Recorder:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.jobs: list[JobMessage] = []
        self.fail_on = fail_on or set()

    async def __call__(self, job: JobMessage) -> None:
        if job.delivery_id in self.fail_on:
            msg = "handler exploded"
            raise RuntimeError(msg)
        self.jobs.append(job)
