from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Career Guidance System"
    VERSION: str = "0.1.0"
    DATABASE_URL: str  # required, no default: fail fast at startup rather than silently using the wrong DB

    # Guards data-mutating dev/demo endpoints (e.g. /market/seed-demo-data).
    # Set to false via env var in production deployments.
    ENABLE_SEED_ENDPOINT: bool = True

    # Path is resolved relative to the process's current working directory,
    # not this file — the app must be run with cwd=app/ (see README) or this
    # silently falls back to real environment variables only.
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
