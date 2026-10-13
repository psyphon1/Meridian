import json
import logging
from collections.abc import Iterator

import pytest
import structlog
from opentelemetry.sdk.trace import TracerProvider
from packages.config.settings import Settings
from packages.observability.logging import (
    REDACTED,
    add_trace_context,
    bind_delivery_id,
    clear_delivery_id,
    get_logger,
    normalize_log_level,
    redact_processor,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    base = {
        "GITHUB_APP_ID": "1",
        "GITHUB_PRIVATE_KEY": "k",
        "GITHUB_WEBHOOK_SECRET": "s",
        "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/meridian",
        **env,
    }
    for name, value in base.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_redact_processor_masks_sensitive_keys():
    event = {
        "event": "webhook.received",
        "Authorization": "Bearer abc",
        "x-hub-signature-256": "sha256=dead",
        "github_token": "ghs_x",
        "token": "t",
        "private_key": "-----BEGIN",
        "api_key": "sk-1",
        "client_secret": "s",
        "payload": {"a": 1},
        "diff": "+code",
        "prompt": "do things",
        "delivery_id": "d-1",
        "tokens_used": 42,
    }
    out = redact_processor(None, "info", event)
    for key in event:
        if key in {"event", "delivery_id", "tokens_used"}:
            assert out[key] == event[key]
        else:
            assert out[key] == REDACTED, key


def test_redact_processor_masks_nested_values():
    out = redact_processor(
        None,
        "info",
        {
            "event": "x",
            "request": {"headers": {"authorization": "Bearer x"}, "n": 1},
            "items": [{"secret": "s"}],
        },
    )
    assert out["request"] == {"headers": {"authorization": REDACTED}, "n": 1}
    assert out["items"] == [{"secret": REDACTED}]


def test_add_trace_context_uses_current_span():
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("op") as span:
        out = add_trace_context(None, "info", {"event": "x"})
        ctx = span.get_span_context()
    assert out["trace_id"] == format(ctx.trace_id, "032x")
    assert out["span_id"] == format(ctx.span_id, "016x")


def test_add_trace_context_without_span_adds_nothing():
    out = add_trace_context(None, "info", {"event": "x"})
    assert "trace_id" not in out


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("info", logging.INFO), (" DEBUG ", logging.DEBUG), ("Warning", logging.WARNING)],
)
def test_normalize_log_level(raw: str, expected: int):
    assert normalize_log_level(raw) == expected


def test_normalize_log_level_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid log level"):
        normalize_log_level("loud")


def test_setup_logging_production_emits_redacted_json_with_correlation(monkeypatch, capsys):
    setup_logging(_settings(monkeypatch, APP_ENV="production", LOG_LEVEL="debug"))
    tracer = TracerProvider().get_tracer("test")

    bind_delivery_id("delivery-123")
    with tracer.start_as_current_span("op") as span:
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            get_logger("t").error("failed", authorization="Bearer abc", exc_info=True)
        trace_id = format(span.get_span_context().trace_id, "032x")

    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["event"] == "failed"
    assert record["level"] == "error"
    assert record["logger"] == "t"
    assert record["authorization"] == REDACTED
    assert record["delivery_id"] == "delivery-123"
    assert record["trace_id"] == trace_id
    assert "RuntimeError: boom" in record["exception"]
    assert "Bearer abc" not in json.dumps(record)


def test_clear_delivery_id_removes_correlation(monkeypatch, capsys):
    setup_logging(_settings(monkeypatch, APP_ENV="production"))
    bind_delivery_id("d-1")
    clear_delivery_id()
    get_logger("t").info("evt")
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "delivery_id" not in record


def test_log_level_filters_lower_levels(monkeypatch, capsys):
    setup_logging(_settings(monkeypatch, APP_ENV="production", LOG_LEVEL="warning"))
    log = get_logger("t")
    log.info("hidden")
    log.warning("shown")
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["shown"]


def test_setup_logging_invalid_level_raises(monkeypatch):
    with pytest.raises(ValueError, match="Invalid log level"):
        setup_logging(_settings(monkeypatch, LOG_LEVEL="loud"))
