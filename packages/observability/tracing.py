"""OpenTelemetry helpers for propagating trace context across the Redis boundary (ADR-006)."""

from opentelemetry import propagate, trace
from opentelemetry.context import Context


def get_tracer(name: str) -> trace.Tracer:
    """Return an OpenTelemetry tracer for the given instrumentation scope name."""
    return trace.get_tracer(name)


def inject_traceparent() -> str | None:
    """Inject the current span context into a W3C ``traceparent`` string.

    Returns None if there is no valid active span (e.g., in tests).
    """
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def extract_traceparent(carrier: dict[str, str]) -> str | None:
    """Return the raw ``traceparent`` string from a carrier dict, or None if absent.

    This does not build a context; use :func:`extract_context` for that.
    """
    return carrier.get("traceparent") if carrier else None


def extract_context(carrier: dict[str, str]) -> Context:
    """Extract an OpenTelemetry ``Context`` from a carrier (e.g. ``{"traceparent": ...}``).

    Pass the result as ``context=`` to ``tracer.start_as_current_span`` so the
    worker's span becomes a child of the API-side span.
    """
    return propagate.extract(carrier)
