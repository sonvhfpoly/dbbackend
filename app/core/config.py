from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Career Guidance System"
    VERSION: str = "0.1.0"
    DATABASE_URL: str  # required, no default: fail fast at startup rather than silently using the wrong DB

    # Guards data-mutating dev/demo endpoints (e.g. /market/seed-demo-data).
    # Set to false via env var in production deployments.
    ENABLE_SEED_ENDPOINT: bool = True

    # FPT Cloud Marketplace chat-completions API (OpenAI-compatible), used by
    # domains/chatbot. Optional (unlike DATABASE_URL): the rest of the app must
    # keep working even if the chatbot isn't configured yet in this environment.
    FPT_CLOUD_API_KEY: Optional[str] = None
    FPT_CLOUD_BASE_URL: str = "https://mkp-api.fptcloud.com"
    FPT_CLOUD_CHAT_MODEL: str = "gemma-4-31B-it"

    # Path is resolved relative to the process's current working directory,
    # not this file — the app must be run with cwd=app/ (see README) or this
    # silently falls back to real environment variables only.
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
