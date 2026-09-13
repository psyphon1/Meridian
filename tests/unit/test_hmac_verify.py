import hashlib
import hmac

from packages.security.hmac_verify import verify_signature


def test_valid_signature_returns_true():
    body = b'{"action":"opened"}'
    secret = "mysecret"  # noqa: S105 — fake test value
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, expected, secret) is True


def test_invalid_signature_returns_false():
    assert verify_signature(b"body", "sha256=deadbeef", "secret") is False


def test_wrong_secret_returns_false():
    body = b"body"
    sig = "sha256=" + hmac.new(b"correct", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "wrong") is False


def test_missing_sha_prefix_returns_false():
    assert verify_signature(b"body", "deadbeef", "secret") is False
