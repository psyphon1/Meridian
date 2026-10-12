"""Timing-safe verification of GitHub's ``X-Hub-Signature-256`` webhook header."""

import hashlib
import hmac


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify an ``X-Hub-Signature-256`` header using a timing-safe comparison.

    Returns ``False`` on any mismatch, including empty, malformed, or non-ASCII
    headers; the caller decides the HTTP status. Both sides are compared as
    bytes because ``hmac.compare_digest`` raises ``TypeError`` for non-ASCII
    ``str`` arguments. Un-encodable input (e.g. lone surrogates) is replaced,
    which can never equal the all-ASCII expected value.
    """
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(
        expected.encode("utf-8"),
        signature_header.encode("utf-8", errors="replace"),
    )
