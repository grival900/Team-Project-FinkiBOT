from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = "postgresql+psycopg://finkibot:finkibot@localhost:5432/finkibot"

    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"

    # Fallback provider when Gemini is out of quota. Free key: https://console.groq.com/keys
    groq_api_key: str = ""
    # llama-3.3-70b was removed from Groq; gpt-oss-120b handles our tool calls well.
    groq_model: str = "openai/gpt-oss-120b"
    # Default only - the admin panel can change it (site_settings table).
    llm_provider: str = "gemini"

    embedding_model_name: str = "BAAI/bge-m3"

    # Chunks below this similarity are ignored by the chat. On-topic chunks score
    # ~0.45-0.8, a name mentioned in passing ~0.33-0.40.
    chat_min_score: float = 0.40

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "FinkiBOT <noreply@finkibot.local>"
    smtp_use_tls: bool = False

    app_base_url: str = "http://localhost:8000"

    scrape_user_agent: str = "FinkiBOT/0.1"
    scrape_request_delay_seconds: float = 1.0
    scrape_announcement_limit: int | None = None
    # One request per syllabus page, so this caps it per run (None = all).
    scrape_subjects_limit: int | None = 30

    @field_validator("scrape_announcement_limit", "scrape_subjects_limit", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        return None if value == "" else value

    frontend_origin: str = "http://localhost:8080"

    enable_scheduler: bool = True
    scheduler_interval_minutes: int = 60
    # Weekly - the slow scrapers make 100+ requests and the pages rarely change.
    scheduler_slow_interval_minutes: int = 10080

    # Required. Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str
    jwt_expires_minutes: int = 1440  # 24h


@lru_cache
def get_settings() -> Settings:
    return Settings()
