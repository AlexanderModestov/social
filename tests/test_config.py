import pytest
from bot.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")

    settings = Settings()

    assert settings.telegram_bot_token == "test_token"
    assert settings.anthropic_api_key == "test_claude"
    assert settings.google_api_key == "test_google"
    assert settings.database_url == "postgresql+asyncpg://x:y@localhost/z"


def test_settings_raises_on_missing_env(monkeypatch):
    for key in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(Exception):
        Settings()
