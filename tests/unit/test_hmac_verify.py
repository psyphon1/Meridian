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


def test_non_ascii_header_returns_false_without_raising():
    assert verify_signature(b"body", "sha256=é☃" + "a" * 60, "secret") is False


def test_lone_surrogate_header_returns_false_without_raising():
    assert verify_signature(b"body", "sha256=\ud800", "secret") is False


def test_empty_header_returns_false():
    assert verify_signature(b"body", "", "secret") is False


def test_empty_body_valid_signature_returns_true():
    secret = "mysecret"  # noqa: S105 — fake test value
    sig = "sha256=" + hmac.new(secret.encode(), b"", hashlib.sha256).hexdigest()
    assert verify_signature(b"", sig, secret) is True


def test_empty_body_with_wrong_signature_returns_false():
    assert verify_signature(b"", "sha256=deadbeef", "secret") is False


def test_wrong_prefix_returns_false():
    digest = hmac.new(b"secret", b"body", hashlib.sha256).hexdigest()
    assert verify_signature(b"body", "sha1=" + digest, "secret") is False
    assert verify_signature(b"body", "SHA256=" + digest, "secret") is False
