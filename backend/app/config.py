"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-insecure-session-secret-change-me"


class Settings(BaseSettings):
    """Typed app configuration. Env var names are case-insensitive (ENV, DATABASE_URL, ...)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./local.db"
    session_secret: str = DEV_SESSION_SECRET
    max_upload_mb: int = 2
    seed_on_start: bool = True

    @model_validator(mode="after")
    def require_secret_in_production(self) -> "Settings":
        """Refuse to start in production with the built-in dev session secret."""
        if self.is_production and self.session_secret == DEV_SESSION_SECRET:
            raise ValueError("SESSION_SECRET must be set in production")
        return self

    @property
    def is_production(self) -> bool:
        """True when running with ENV=production."""
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance."""
    return Settings()
