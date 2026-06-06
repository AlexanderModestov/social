import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    gcp_project_id: str
    gcp_location: str = "us-central1"
    google_application_credentials_json: Optional[str] = None
    database_url: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Bootstrap Application Default Credentials in environments (Railway) that pass
# the service-account key as JSON contents rather than a mounted file.
if settings.google_application_credentials_json:
    _sa_path = Path(tempfile.gettempdir()) / "gcp_sa.json"
    _sa_path.write_text(settings.google_application_credentials_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_sa_path)
