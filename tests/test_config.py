import os
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
