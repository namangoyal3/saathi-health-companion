from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    # Railway's Postgres plugin injects DATABASE_URL as `postgresql://…`
    # SQLAlchemy async requires the `postgresql+asyncpg://…` driver prefix.
    # Normalize so either form works in .env or in Railway env.
    database_url: str = "postgresql+asyncpg://saath:saath@localhost:5432/saath"

    @field_validator("database_url", mode="before")
    @classmethod
    def _ensure_async_driver(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

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

    # FreeSWITCH ESL (replaces Twilio as second IVR provider)
    fs_esl_host: str = ""
    fs_esl_port: int = 8021
    fs_esl_password: str = "change-me-esl"
    fs_sip_gateway: str = "pstn"  # sofia profile gateway name in FS config
    fs_caller_id: str = ""  # outbound CLI shown to senior

    # IVR (Day 3)
    ivr_provider: str = "exotel"  # 'exotel' | 'freeswitch'
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

    # NVIDIA NIM (OpenAI-compatible, free tier)
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/llama-3.3-nemotron-super-49b-v1"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # OpenRouter (reliable OpenAI-compatible gateway)
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ElevenLabs (web chat voice)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel — clear, calm

    # Groq (free Whisper v3 for Telegram voice STT)
    groq_api_key: str = ""
    groq_whisper_model: str = "whisper-large-v3-turbo"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Langfuse (optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    environment: str = "development"


settings = Settings()
