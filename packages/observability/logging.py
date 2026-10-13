"""Meridian structured logging: JSON/console rendering, redaction, correlation IDs."""

import logging
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, FilteringBoundLogger, Processor, WrappedLogger

from packages.config.settings import Settings

REDACTED = "[REDACTED]"

# Key fragments that always indicate sensitive data.
_SENSITIVE_FRAGMENTS: tuple[str, ...] = (
    "authorization",
    "secret",
    "private_key",
    "api_key",
    "signature",
    "password",
    "credential",
)
# Generic words matched only as the whole key or a ``_``-suffix, so that
# metrics such as ``tokens_used`` or ``prompt_tokens`` are not redacted.
_SENSITIVE_WORDS: tuple[str, ...] = ("token", "payload", "diff", "prompt")


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS):
        return True
    return any(normalized == word or normalized.endswith(f"_{word}") for word in _SENSITIVE_WORDS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: REDACTED if isinstance(k, str) and _is_sensitive(k) else _redact_value(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    return value


def redact_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> MutableMapping[str, Any]:
    """structlog processor: replace values of sensitive keys (recursively) with ``[REDACTED]``."""
    return {k: REDACTED if _is_sensitive(k) else _redact_value(v) for k, v in event_dict.items()}


def add_trace_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> MutableMapping[str, Any]:
    """structlog processor: add ``trace_id``/``span_id`` of the current OTel span, if valid."""
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = trace.format_trace_id(ctx.trace_id)
        event_dict["span_id"] = trace.format_span_id(ctx.span_id)
    return event_dict


def bind_delivery_id(delivery_id: str) -> None:
    """Bind ``X-GitHub-Delivery`` to the current context so every log line carries it."""
    structlog.contextvars.bind_contextvars(delivery_id=delivery_id)


def clear_delivery_id() -> None:
    """Remove ``delivery_id`` from the current logging context."""
    structlog.contextvars.unbind_contextvars("delivery_id")


def normalize_log_level(level: str) -> int:
    """Convert a level name (case-insensitive) to its numeric value.

    Raises:
        ValueError: if ``level`` is not a known logging level name.
    """
    value = logging.getLevelNamesMapping().get(level.strip().upper())
    if value is None:
        raise ValueError(f"Invalid log level: {level!r}")
    return value


def setup_logging(settings: Settings) -> None:
    """Configure structlog: JSON in production, console elsewhere.

    The same normalized numeric level is applied to stdlib logging and the
    structlog filtering logger.
    """
    level = normalize_log_level(settings.log_level)
    logging.basicConfig(format="%(message)s", level=level)
    production = settings.app_env == "production"
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_trace_context,
        redact_processor,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if production:
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> FilteringBoundLogger:
    """Return a structlog logger with ``logger=<name>`` bound to every event."""
    logger: FilteringBoundLogger = structlog.get_logger().bind(logger=name)
    return logger
