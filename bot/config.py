from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    google_api_key: str
    database_url: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
