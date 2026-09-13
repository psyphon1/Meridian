from packages.observability.tracing import extract_traceparent, inject_traceparent


def test_inject_returns_string_or_none():
    result = inject_traceparent()
    assert result is None or isinstance(result, str)


def test_extract_from_carrier():
    carrier = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    result = extract_traceparent(carrier)
    assert result == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_extract_missing_returns_none():
    assert extract_traceparent({}) is None
