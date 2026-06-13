import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    gcp_project_id: str
    gcp_location: str = "us-central1"
    veo_model: str = "veo-3.1-generate-001"
    gcs_output_bucket: Optional[str] = None
    apify_token: Optional[str] = None
    publora_api_key: Optional[str] = None
    linkedin_platform_id: Optional[str] = None
    google_application_credentials_json: Optional[str] = None
    database_url: str
    # Comma/space-separated Telegram user IDs allowed to use the bot.
    # Empty/unset => no one is allowed (fail-closed).
    allowed_user_ids: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def allowed_users(self) -> set[int]:
        """Parse `allowed_user_ids` into a set of Telegram user IDs.

        Accepts comma- and/or whitespace-separated integers; non-numeric tokens
        are ignored. An empty/unset value yields an empty set (fail-closed).
        """
        ids: set[int] = set()
        for token in (self.allowed_user_ids or "").replace(",", " ").split():
            try:
                ids.add(int(token))
            except ValueError:
                continue
        return ids


settings = Settings()

# Bootstrap Application Default Credentials in environments (Railway) that pass
# the service-account key as JSON contents rather than a mounted file.
if settings.google_application_credentials_json:
    try:
        json.loads(settings.google_application_credentials_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON; "
            "ensure the service-account key was pasted as a single line."
        ) from exc
    _sa_path = Path(tempfile.gettempdir()) / "gcp_sa.json"
    _sa_path.write_text(settings.google_application_credentials_json)
    os.chmod(_sa_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 — owner read/write only
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_sa_path)
