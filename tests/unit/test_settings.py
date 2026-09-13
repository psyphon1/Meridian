import pytest
from pydantic import ValidationError

_FAKE_RSA_KEY = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", _FAKE_RSA_KEY)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsecret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/meridian")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from packages.config.settings import Settings

    s = Settings()
    assert s.github_app_id == 12345
    assert s.github_webhook_secret == "whsecret"  # noqa: S105 — fake test value
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.app_env == "development"
    assert s.log_level == "INFO"


def test_settings_missing_required_raises(monkeypatch):
    for k in ("GITHUB_APP_ID", "GITHUB_PRIVATE_KEY", "GITHUB_WEBHOOK_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    from packages.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_invalid_app_id_raises(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "not-an-int")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "key")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/meridian")
    from packages.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings()
