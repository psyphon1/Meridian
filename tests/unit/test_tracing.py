from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer
from packages.observability.tracing import (
    extract_context,
    extract_traceparent,
    get_tracer,
    inject_traceparent,
)

TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@pytest.fixture
def exporter_and_tracer() -> Iterator[tuple[InMemorySpanExporter, Tracer]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter, provider.get_tracer("test")
    provider.shutdown()


def test_inject_without_active_span_returns_none():
    assert inject_traceparent() is None


def test_inject_extract_roundtrip_links_child_span_to_parent(exporter_and_tracer):
    exporter, tracer = exporter_and_tracer

    with tracer.start_as_current_span("webhook.receive") as parent:
        traceparent = inject_traceparent()
    assert traceparent is not None

    ctx = extract_context({"traceparent": traceparent})
    with tracer.start_as_current_span("worker.process", context=ctx) as child:
        pass

    assert child.get_span_context().trace_id == parent.get_span_context().trace_id
    assert child.parent is not None
    assert child.parent.span_id == parent.get_span_context().span_id
    assert child.parent.is_remote is True
    assert {s.name for s in exporter.get_finished_spans()} == {"webhook.receive", "worker.process"}


def test_extract_context_from_known_traceparent(exporter_and_tracer):
    _, tracer = exporter_and_tracer
    ctx = extract_context({"traceparent": TRACEPARENT})
    with tracer.start_as_current_span("worker.process", context=ctx) as span:
        pass
    assert format(span.get_span_context().trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_extract_context_missing_traceparent_starts_new_trace(exporter_and_tracer):
    _, tracer = exporter_and_tracer
    with tracer.start_as_current_span("worker.process", context=extract_context({})) as span:
        pass
    assert span.parent is None


def test_extract_context_malformed_traceparent_does_not_raise(exporter_and_tracer):
    _, tracer = exporter_and_tracer
    with tracer.start_as_current_span(
        "worker.process", context=extract_context({"traceparent": "garbage"})
    ) as span:
        pass
    assert span.parent is None


def test_extract_traceparent_returns_raw_value():
    assert extract_traceparent({"traceparent": TRACEPARENT}) == TRACEPARENT


def test_extract_traceparent_missing_returns_none():
    assert extract_traceparent({}) is None


def test_get_tracer_returns_tracer():
    assert hasattr(get_tracer("meridian.test"), "start_as_current_span")
