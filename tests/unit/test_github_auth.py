from packages.github.auth import generate_app_jwt


def test_generate_app_jwt_structure(monkeypatch):
    # This test uses a mock to avoid needing a real RSA key
    monkeypatch.setattr("packages.github.auth.jwt.encode", lambda p, k, algorithm: "mock.jwt.token")
    token = generate_app_jwt("fake-key", 12345)
    assert token == "mock.jwt.token"  # noqa: S105 — fake test value


def test_generate_app_jwt_payload(monkeypatch):
    captured = {}

    def fake_encode(payload, key, algorithm):
        captured.update(payload)
        return "mock.jwt.token"

    monkeypatch.setattr("packages.github.auth.jwt.encode", fake_encode)
    generate_app_jwt("fake-key", 12345)
    assert captured["iss"] == "12345"  # str: PyJWT >= 2.10 requires it
    assert captured["exp"] - captured["iat"] == 660  # 600 + 60 skew


def test_generate_app_jwt_real_signature_roundtrip():
    """Unmocked: PyJWT >= 2.10 raises TypeError for an int `iss` — guard against regressions."""
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    claims = jwt.decode(generate_app_jwt(priv, 777), pub, algorithms=["RS256"])
    assert claims["iss"] == "777"
