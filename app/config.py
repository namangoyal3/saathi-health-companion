from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://saath:saath@localhost:5432/saath"

    # Redis / arq
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str = ""
    model_opus: str = "claude-opus-4-7"
    model_haiku: str = "claude-haiku-4-5-20251001"

    # Memory filesystem
    memory_root: Path = Path("./data/memories")

    # Auth
    jwt_secret: str = "change-me-in-production-must-be-at-least-64-characters-long-xx"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Telegram
    telegram_bot_token: str = ""

    # Exotel (Day 3)
    exotel_sid: str = ""
    exotel_token: str = ""
    exotel_from_number: str = ""

    # Twilio (Day 3)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # IVR (Day 3)
    app_base_url: str = "http://localhost:8080"
    exotel_webhook_secret: str = "change-me-ivr-webhook-secret"
    sarvam_api_key: str = ""
    google_application_credentials: str = ""

    # Wearable (Day 3)
    wearable_hmac_secret: str = "change-me-wearable-hmac-secret"

    # Storage (Day 4)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "saath-reports"

    # Langfuse (optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    environment: str = "development"


settings = Settings()
