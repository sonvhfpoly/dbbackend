from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Career Guidance System"
    VERSION: str = "0.1.0"
    DATABASE_URL: str  # required, no default: fail fast at startup rather than silently using the wrong DB

    # Guards data-mutating dev/demo endpoints (e.g. /market/seed-demo-data).
    # Set to false via env var in production deployments.
    ENABLE_SEED_ENDPOINT: bool = True

    # Dev/demo convenience: auto-create any missing tables at startup via
    # Base.metadata.create_all() so a fresh local/demo DB works without first
    # running `alembic upgrade head` by hand. Schema changes are still owned
    # by Alembic (app/alembic/) — this is purely additive and a no-op once
    # every table already exists, so it never substitutes for writing a real
    # migration. Set to false in any shared/production deployment, where
    # `alembic upgrade head` should be the only thing allowed to change schema.
    AUTO_CREATE_SCHEMA: bool = True

    # FPT Cloud Marketplace chat-completions API (OpenAI-compatible), used by
    # domains/chatbot. Optional (unlike DATABASE_URL): the rest of the app must
    # keep working even if the chatbot isn't configured yet in this environment.
    FPT_CLOUD_API_KEY: Optional[str] = None
    FPT_CLOUD_BASE_URL: str = "https://mkp-api.fptcloud.com"
    FPT_CLOUD_CHAT_MODEL: str = "gemma-4-31B-it"

    # Vertex AI (Gemini) — preferred over FPT Cloud when Application Default
    # Credentials and a project can be resolved (always true on Cloud Run with
    # a service account attached: credentials load automatically, no key to
    # manage). VERTEX_PROJECT_ID is optional; unset it to auto-detect the
    # project from ADC. See domains/chatbot/providers.py for the fallback logic.
    VERTEX_PROJECT_ID: Optional[str] = None
    VERTEX_LOCATION: str = "asia-southeast1"
    VERTEX_MODEL: str = "gemini-2.5-flash"

    # GCS bucket the AI Task Builder (domains/task_builder) uploads enterprise
    # documents to. Reuses the same ADC/service account as Vertex AI above —
    # no separate credentials to manage on Cloud Run. Optional: document
    # upload returns 503 until this is set, same convention as FPT_CLOUD_API_KEY.
    TASK_BUILDER_GCS_BUCKET: Optional[str] = None

    # Path is resolved relative to the process's current working directory,
    # not this file — the app must be run with cwd=app/ (see README) or this
    # silently falls back to real environment variables only.
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
