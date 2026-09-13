import hashlib
import hmac


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-Hub-Signature-256 header using timing-safe comparison.

    Returns False on any mismatch (never raises — caller decides status code).
    """
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
