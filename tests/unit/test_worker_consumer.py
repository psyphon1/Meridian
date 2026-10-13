"""Unit tests for the worker consumer (ack-after-commit, redelivery, dead-letter, shutdown)."""

import asyncio
import re
from typing import Any

import pytest
from apps.worker import consumer as c
from apps.worker.consumer import DeliveryPayloadMissingError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from packages.config.redis import (
    CONSUMER_GROUP,
    STREAM_DEADLETTER,
    STREAM_HIGH,
    STREAM_LOW,
    STREAM_MEDIUM,
)
from packages.models.schemas import JobMessage
from redis.exceptions import RedisError, ResponseError
from tests.fakes import FakeRedis, FakeSessionFactory, eventually


def _job(delivery_id: str = "d1", traceparent: str | None = None) -> JobMessage:
    return JobMessage(
        delivery_id=delivery_id,
        event="pull_request",
        action="opened",
        installation_id=1,
        repository_id=2,
        repository_full_name="o/r",
        pr_number=3,
        pr_title="t",
        head_sha="h",
        base_sha="b",
        traceparent=traceparent,
        enqueued_at="2026-09-13T12:00:00Z",
    )


class _Delivery:
    id = 7


async def _redis_with_groups() -> FakeRedis:
    r = FakeRedis()
    await c.ensure_groups(r)  # type: ignore[arg-type]
    return r


def test_flatten_read_shapes() -> None:
    assert c.flatten_read(None) == []
    assert c.flatten_read([]) == []
    assert c.flatten_read([["s", [("1-0", {"data": "x"})]]]) == [("s", "1-0", {"data": "x"})]
    assert c.flatten_read({b"s": [(b"1-0", {b"data": b"x"})]}) == [("s", "1-0", {"data": "x"})]
    assert c.flatten_read([["s", [("1-0", None)]]]) == [("s", "1-0", None)]


async def test_ensure_groups_is_idempotent_and_surfaces_other_errors() -> None:
    r = await _redis_with_groups()
    await c.ensure_groups(r)  # type: ignore[arg-type]  # BUSYGROUP swallowed
    assert set(r.groups) == {STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW}

    class Broken(FakeRedis):
        async def xgroup_create(self, *a: Any, **k: Any) -> bool:
            raise ResponseError("ERR wrong")

    with pytest.raises(ResponseError):
        await c.ensure_groups(Broken())  # type: ignore[arg-type]


async def test_process_job_marks_processed_and_logs(capsys: pytest.CaptureFixture[str]) -> None:
    factory = FakeSessionFactory(rows=[_Delivery()])
    await c.process_job(_job("abc"), factory, STREAM_MEDIUM)  # type: ignore[arg-type]
    kinds = [type(s).__name__ for s in factory.statements]
    assert kinds == ["Select", "Update"]
    out = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)  # strip ANSI colours
    assert "job_processed" in out
    assert "delivery_id=abc" in out
    assert f"stream={STREAM_MEDIUM}" in out
    assert "duration_ms=" in out


async def test_process_job_missing_delivery_raises() -> None:
    with pytest.raises(DeliveryPayloadMissingError):
        await c.process_job(_job(), FakeSessionFactory(rows=[]), STREAM_MEDIUM)  # type: ignore[arg-type]


async def test_process_job_continues_trace_from_traceparent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(c, "_tracer", provider.get_tracer("test"))
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    tp = f"00-{trace_id}-00f067aa0ba902b7-01"
    await c.process_job(
        _job(traceparent=tp),
        FakeSessionFactory(rows=[_Delivery()]),
        STREAM_HIGH,  # type: ignore[arg-type]
    )
    (span,) = exporter.get_finished_spans()
    assert span.name == "worker.process_job"
    assert format(span.context.trace_id, "032x") == trace_id
    assert span.parent is not None and format(span.parent.span_id, "016x") == "00f067aa0ba902b7"


async def _entry(r: FakeRedis, stream: str, payload: str) -> tuple[str, dict[str, str]]:
    entry_id = await r.xadd(stream, {"data": payload})
    return entry_id, {"data": payload}


async def test_handle_entry_acks_only_after_successful_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = await _redis_with_groups()
    entry_id, fields = await _entry(r, STREAM_MEDIUM, _job().model_dump_json())
    await r.xreadgroup(CONSUMER_GROUP, "w1", {STREAM_MEDIUM: ">"})
    order: list[str] = []

    async def fake_process(job: JobMessage, sf: Any, stream: str) -> None:
        order.append(f"process:{len(r.groups[STREAM_MEDIUM][CONSUMER_GROUP]['pending'])}")

    monkeypatch.setattr(c, "process_job", fake_process)
    ok = await c.handle_entry(r, None, STREAM_MEDIUM, entry_id, fields)  # type: ignore[arg-type]
    assert ok is True
    assert order == ["process:1"]  # still pending while processing
    assert r.groups[STREAM_MEDIUM][CONSUMER_GROUP]["pending"] == {}
    # A second XACK (e.g. PR #4's ack inside process_message) is harmless.
    assert await r.xack(STREAM_MEDIUM, CONSUMER_GROUP, entry_id) == 0


async def test_handle_entry_failure_leaves_entry_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    r = await _redis_with_groups()
    entry_id, fields = await _entry(r, STREAM_MEDIUM, _job().model_dump_json())
    await r.xreadgroup(CONSUMER_GROUP, "w1", {STREAM_MEDIUM: ">"})

    async def boom(job: JobMessage, sf: Any, stream: str) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(c, "process_job", boom)
    assert await c.handle_entry(r, None, STREAM_MEDIUM, entry_id, fields) is False  # type: ignore[arg-type]
    assert entry_id in r.groups[STREAM_MEDIUM][CONSUMER_GROUP]["pending"]


async def test_handle_entry_invalid_message_is_dead_lettered() -> None:
    r = await _redis_with_groups()
    entry_id, fields = await _entry(r, STREAM_LOW, "{not json")
    await r.xreadgroup(CONSUMER_GROUP, "w1", {STREAM_LOW: ">"})
    assert await c.handle_entry(r, None, STREAM_LOW, entry_id, fields) is False  # type: ignore[arg-type]
    assert r.groups[STREAM_LOW][CONSUMER_GROUP]["pending"] == {}
    assert r.streams[STREAM_DEADLETTER][0][1]["reason"] == "invalid_job_message"


async def test_handle_entry_deleted_entry_is_acked() -> None:
    r = await _redis_with_groups()
    entry_id, _ = await _entry(r, STREAM_LOW, "x")
    await r.xreadgroup(CONSUMER_GROUP, "w1", {STREAM_LOW: ">"})
    assert await c.handle_entry(r, None, STREAM_LOW, entry_id, None) is False  # type: ignore[arg-type]
    assert r.groups[STREAM_LOW][CONSUMER_GROUP]["pending"] == {}


async def test_handle_entry_ack_failure_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    r = await _redis_with_groups()
    entry_id, fields = await _entry(r, STREAM_MEDIUM, _job().model_dump_json())

    async def ok(job: JobMessage, sf: Any, stream: str) -> None:
        return None

    async def bad_ack(*a: Any) -> int:
        raise RedisError("conn reset")

    monkeypatch.setattr(c, "process_job", ok)
    monkeypatch.setattr(r, "xack", bad_ack)
    assert await c.handle_entry(r, None, STREAM_MEDIUM, entry_id, fields) is False  # type: ignore[arg-type]


async def _run_until(r: FakeRedis, predicate: Any, *, within_s: float = 5.0) -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(c.run_consumer_loop(r, None, "w1", stop))  # type: ignore[arg-type]
    try:
        await eventually(predicate, within_s=within_s)
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


async def test_loop_processes_in_priority_order_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    r = await _redis_with_groups()
    seen: list[str] = []
    await r.xadd(STREAM_LOW, {"data": _job("low").model_dump_json()})
    await r.xadd(STREAM_MEDIUM, {"data": _job("med").model_dump_json()})
    await r.xadd(STREAM_HIGH, {"data": _job("high").model_dump_json()})

    async def record(job: JobMessage, sf: Any, stream: str) -> None:
        seen.append(job.delivery_id)

    monkeypatch.setattr(c, "process_job", record)
    await _run_until(r, lambda: len(seen) == 3)
    assert seen == ["high", "med", "low"]
    for stream in (STREAM_HIGH, STREAM_MEDIUM, STREAM_LOW):
        assert r.groups[stream][CONSUMER_GROUP]["pending"] == {}  # all acked


async def test_failing_job_does_not_kill_loop_and_is_retried_then_dead_lettered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = await _redis_with_groups()
    attempts = {"n": 0}
    await r.xadd(STREAM_MEDIUM, {"data": _job("poison").model_dump_json()})
    await r.xadd(STREAM_MEDIUM, {"data": _job("good").model_dump_json()})
    good: list[str] = []

    async def flaky(job: JobMessage, sf: Any, stream: str) -> None:
        if job.delivery_id == "poison":
            attempts["n"] += 1
            raise RuntimeError("always fails")
        good.append(job.delivery_id)

    monkeypatch.setattr(c, "process_job", flaky)
    monkeypatch.setattr(c, "BACKLOG_INTERVAL_S", 0.0)
    await _run_until(r, lambda: bool(r.streams.get(STREAM_DEADLETTER)) and good == ["good"])
    assert attempts["n"] == 3  # tried exactly MAX_DELIVERIES times
    dead = r.streams[STREAM_DEADLETTER][0][1]
    assert dead["reason"] == "max_deliveries_exceeded"
    assert r.groups[STREAM_MEDIUM][CONSUMER_GROUP]["pending"] == {}


async def test_backlog_redelivers_entries_reclaimed_by_janitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = await _redis_with_groups()
    await r.xadd(STREAM_MEDIUM, {"data": _job("orphan").model_dump_json()})
    await r.xreadgroup(CONSUMER_GROUP, "crashed-worker", {STREAM_MEDIUM: ">"})
    r.advance(10_000)
    await r.xautoclaim(STREAM_MEDIUM, CONSUMER_GROUP, "w1", min_idle_time=1000)
    seen: list[str] = []

    async def record(job: JobMessage, sf: Any, stream: str) -> None:
        seen.append(job.delivery_id)

    monkeypatch.setattr(c, "process_job", record)
    await _run_until(r, lambda: seen == ["orphan"])
    assert r.groups[STREAM_MEDIUM][CONSUMER_GROUP]["pending"] == {}


async def test_loop_survives_redis_errors_with_backoff_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = await _redis_with_groups()
    calls = {"n": 0}
    stop = asyncio.Event()

    def hook() -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RedisError("connection refused")
        stop.set()

    r.xreadgroup_hook = hook
    monkeypatch.setattr(c, "_ERROR_BACKOFF_S", 0.001)
    await asyncio.wait_for(c.run_consumer_loop(r, None, "w1", stop), 5)  # type: ignore[arg-type]
    assert calls["n"] >= 3


async def test_loop_exits_immediately_when_stop_already_set() -> None:
    r = await _redis_with_groups()
    stop = asyncio.Event()
    stop.set()
    await asyncio.wait_for(c.run_consumer_loop(r, None, "w1", stop), 2)  # type: ignore[arg-type]


async def test_job_failure_logs_only_error_type_without_traceback_or_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    r = await _redis_with_groups()
    entry_id, fields = await _entry(r, STREAM_MEDIUM, _job("dlv-9").model_dump_json())
    await r.xreadgroup(CONSUMER_GROUP, "w1", {STREAM_MEDIUM: ">"})

    async def boom(job: JobMessage, sf: Any, stream: str) -> None:
        raise RuntimeError("secret-payload-content")

    monkeypatch.setattr(c, "process_job", boom)
    assert await c.handle_entry(r, None, STREAM_MEDIUM, entry_id, fields) is False  # type: ignore[arg-type]
    captured = capsys.readouterr()
    out = re.sub(r"\x1b\[[0-9;]*m", "", captured.out + captured.err)
    assert "job_failed" in out
    assert "delivery_id=dlv-9" in out
    assert "error_type=RuntimeError" in out
    assert "secret-payload-content" not in out
    assert "Traceback" not in out
