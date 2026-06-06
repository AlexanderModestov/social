import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
