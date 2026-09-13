from opentelemetry import propagate


def inject_traceparent() -> str | None:
    """Inject the current span context into a traceparent string.

    Returns None if no active span exists (e.g., in tests).
    """
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def extract_traceparent(carrier: dict[str, str]) -> str | None:
    """Extract a traceparent string from a carrier dict (e.g., JobMessage fields)."""
    return carrier.get("traceparent") if carrier else None
