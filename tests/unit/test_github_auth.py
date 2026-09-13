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
    assert captured["iss"] == 12345
    assert captured["exp"] - captured["iat"] == 660  # 600 + 60 skew
