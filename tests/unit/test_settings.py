from collections.abc import Iterator

import pytest
from packages.config.settings import Settings, get_settings
from pydantic import SecretStr, ValidationError

_FAKE_RSA_KEY = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
_DB_URL = "postgresql+psycopg://user:pass@localhost:5432/meridian"


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Set the minimal required environment and clear optional overrides."""
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", _FAKE_RSA_KEY)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsecret")
    monkeypatch.setenv("DATABASE_URL", _DB_URL)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    return monkeypatch


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_loads_from_env(required_env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.github_app_id == 12345
    assert s.github_webhook_secret.get_secret_value() == "whsecret"
    assert s.github_private_key.get_secret_value() == _FAKE_RSA_KEY
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.app_env == "development"
    assert s.log_level == "INFO"


def test_settings_secrets_are_secretstr(required_env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert isinstance(s.github_private_key, SecretStr)
    assert isinstance(s.github_webhook_secret, SecretStr)


def test_settings_repr_and_str_hide_secrets(required_env: pytest.MonkeyPatch) -> None:
    s = Settings()
    for rendered in (repr(s), str(s)):
        assert "whsecret" not in rendered
        assert "fake" not in rendered
        assert "BEGIN RSA PRIVATE KEY" not in rendered
        assert "**********" in rendered


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("GITHUB_APP_ID", "GITHUB_PRIVATE_KEY", "GITHUB_WEBHOOK_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_invalid_app_id_raises(required_env: pytest.MonkeyPatch) -> None:
    required_env.setenv("GITHUB_APP_ID", "not-an-int")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("env", ["development", "staging", "production", "test"])
def test_settings_accepts_valid_app_env(required_env: pytest.MonkeyPatch, env: str) -> None:
    required_env.setenv("APP_ENV", env)
    assert Settings().app_env == env


@pytest.mark.parametrize("env", ["prod", "Production", "", "local"])
def test_settings_rejects_invalid_app_env(required_env: pytest.MonkeyPatch, env: str) -> None:
    required_env.setenv("APP_ENV", env)
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "app_env" in str(exc.value)


def test_get_settings_is_cached(required_env: pytest.MonkeyPatch) -> None:
    first = get_settings()
    required_env.setenv("APP_ENV", "production")
    second = get_settings()
    assert first is second
    assert second.app_env == "development"  # env change after first call is not re-read


def test_get_settings_cache_clear_reloads(required_env: pytest.MonkeyPatch) -> None:
    first = get_settings()
    required_env.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    second = get_settings()
    assert second is not first
    assert second.app_env == "staging"
