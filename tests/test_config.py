import pytest
from bot.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")

    settings = Settings(_env_file=None)

    assert settings.telegram_bot_token == "test_token"
    assert settings.anthropic_api_key == "test_claude"
    assert settings.gcp_project_id == "test-project"
    assert settings.gcp_location == "us-central1"
    assert settings.database_url == "postgresql+asyncpg://x:y@localhost/z"


def test_settings_raises_on_missing_env(monkeypatch):
    for key in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "GCP_PROJECT_ID", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_apify_token_defaults_to_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)

    settings = Settings(_env_file=None)
    assert settings.apify_token is None


def test_apify_token_reads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.setenv("APIFY_TOKEN", "apify_abc123")

    settings = Settings(_env_file=None)
    assert settings.apify_token == "apify_abc123"
