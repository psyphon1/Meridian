"""Unit tests for the transactional outbox publisher (Task 27)."""

import asyncio
from typing import Any

import pytest
from apps.worker import outbox_publisher as op
from apps.worker.outbox_publisher import PublishResult, build_job_message, publish_pending
from packages.config.redis import STREAM_MEDIUM
from packages.models.audit import WebhookDelivery
from redis.exceptions import ConnectionError as RedisConnectionError
from tests.fakes import FakeRedis, FakeSessionFactory


def _payload(**pr_overrides: Any) -> dict[str, Any]:
    pr = {"number": 42, "title": "X", "head": {"sha": "abc"}, "base": {"sha": "def"}}
    pr.update(pr_overrides)
    return {
        "action": "opened",
        "installation": {"id": 12345},
        "repository": {"id": 67890, "full_name": "owner/repo"},
        "pull_request": pr,
    }


def _deliv(delivery_id: str = "d1", row_id: int = 1, **overrides: Any) -> WebhookDelivery:
    values: dict[str, Any] = {
        "id": row_id,
        "delivery_id": delivery_id,
        "event": "pull_request",
        "action": "opened",
        "payload": _payload(),
        "payload_size_bytes": 100,
        "enqueued": False,
    }
    values.update(overrides)
    return WebhookDelivery(**values)


def test_build_job_message_from_delivery() -> None:
    msg = build_job_message(_deliv())
    assert msg.delivery_id == "d1"
    assert msg.event == "pull_request"
    assert msg.action == "opened"
    assert msg.installation_id == 12345
    assert msg.repository_id == 67890
    assert msg.repository_full_name == "owner/repo"
    assert msg.pr_number == 42
    assert msg.pr_title == "X"
    assert msg.head_sha == "abc"
    assert msg.base_sha == "def"
    assert msg.priority == "medium"


def test_build_job_message_tolerates_null_title_and_missing_sections() -> None:
    msg = build_job_message(_deliv(payload=_payload(title=None)))
    assert msg.pr_title == ""
    sparse = build_job_message(_deliv(payload={"installation": {"id": 9}, "pull_request": None}))
    assert (sparse.installation_id, sparse.pr_number, sparse.head_sha) == (9, 0, "")
    junk = build_job_message(_deliv(payload={"pull_request": {"number": True, "head": "x"}}))
    assert (junk.pr_number, junk.head_sha) == (0, "")
    assert build_job_message(_deliv(payload=["not", "a", "dict"])).repository_id == 0  # type: ignore[arg-type]


async def test_publish_pending_xadds_and_marks_each_row() -> None:
    redis = FakeRedis()
    factory = FakeSessionFactory(rows=[_deliv("a", 1), _deliv("b", 2)])
    result = await publish_pending(redis, factory)  # type: ignore[arg-type]
    assert result == PublishResult(published=2, failed=0)
    assert len(redis.streams[STREAM_MEDIUM]) == 2
    assert [type(s).__name__ for s in factory.statements] == ["Select", "Update", "Update"]


async def test_publish_pending_empty_returns_zero() -> None:
    result = await publish_pending(FakeRedis(), FakeSessionFactory(rows=[]))  # type: ignore[arg-type]
    assert result == PublishResult(0, 0)


async def test_invalid_row_is_quarantined_and_does_not_block_others() -> None:
    redis = FakeRedis()
    bad = _deliv("bad", 1, event=None)  # fails JobMessage validation
    good = _deliv("good", 2)
    factory = FakeSessionFactory(rows=[bad, good])
    quarantine: set[str] = set()
    result = await publish_pending(redis, factory, quarantine)  # type: ignore[arg-type]
    assert result == PublishResult(published=1, failed=1)
    assert quarantine == {"bad"}
    assert len(redis.streams[STREAM_MEDIUM]) == 1
    # Only the good row was updated (marked enqueued).
    assert [type(s).__name__ for s in factory.statements] == ["Select", "Update"]


async def test_quarantined_ids_are_excluded_from_the_query() -> None:
    factory = FakeSessionFactory(rows=[])
    await publish_pending(FakeRedis(), factory, {"bad"})  # type: ignore[arg-type]
    assert "NOT IN" in str(factory.statements[0]).upper()


async def test_quarantine_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op, "MAX_QUARANTINE", 0)
    quarantine: set[str] = set()
    result = await publish_pending(
        FakeRedis(),  # type: ignore[arg-type]
        FakeSessionFactory(rows=[_deliv("bad", 1, event=None)]),
        quarantine,
    )
    assert result.failed == 1 and quarantine == set()


async def test_xadd_failure_skips_that_row_only_and_leaves_it_unmarked() -> None:
    class FlakyRedis(FakeRedis):
        async def xadd(self, stream: str, fields: dict[str, str]) -> str:
            if '"delivery_id":"b"' in fields["data"]:
                raise RedisConnectionError("redis down")
            return await super().xadd(stream, fields)

    redis = FlakyRedis()
    factory = FakeSessionFactory(rows=[_deliv("a", 1), _deliv("b", 2), _deliv("c", 3)])
    quarantine: set[str] = set()
    result = await publish_pending(redis, factory, quarantine)  # type: ignore[arg-type]
    assert result == PublishResult(published=2, failed=1)
    assert quarantine == set()  # transient: retried next poll
    assert [type(s).__name__ for s in factory.statements] == ["Select", "Update", "Update"]


async def _run_publisher(monkeypatch: pytest.MonkeyPatch, results: list[Any]) -> list[float]:
    """Drive run_outbox_publisher through scripted results; record requested delays."""
    delays: list[float] = []
    stop = asyncio.Event()
    script = iter(results)

    async def fake_publish(*_a: Any, **_k: Any) -> PublishResult:
        item = next(script)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[no-any-return]

    async def fake_wait(_stop: asyncio.Event, delay: float) -> bool:
        delays.append(delay)
        if len(delays) >= len(results):
            stop.set()
            return True
        return False

    monkeypatch.setattr(op, "publish_pending", fake_publish)
    monkeypatch.setattr(op, "wait_or_stop", fake_wait)
    await asyncio.wait_for(op.run_outbox_publisher(FakeRedis(), FakeSessionFactory(), stop), 5)  # type: ignore[arg-type]
    return delays


async def test_publisher_loop_backs_off_on_errors_and_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = await _run_publisher(
        monkeypatch,
        [
            RuntimeError("db"),
            RuntimeError("db"),
            PublishResult(0, 0),
            PublishResult(1, 1),
            PublishResult(op.BATCH_SIZE, 0),
        ],
    )
    assert delays == [2.0, 4.0, op.POLL_INTERVAL_S, 2.0, 0.0]


async def test_publisher_loop_stops_promptly_when_stop_is_set() -> None:
    stop = asyncio.Event()
    stop.set()
    await asyncio.wait_for(
        op.run_outbox_publisher(FakeRedis(), FakeSessionFactory(), stop),  # type: ignore[arg-type]
        2,
    )
