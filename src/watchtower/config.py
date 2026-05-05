"""Application configuration.

Follows the 12-factor principle: all config comes from the environment.
Locally, values are loaded from a `.env` file (gitignored).
In production, values come from real environment variables.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Pydantic validates types at startup. If a required value is missing
    or the wrong type, the app fails fast with a clear error -- much
    better than a mysterious crash 30 minutes later.
    """

    model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    enable_decoding=False,  # let our field_validator handle list parsing
    )

    # External service credentials (EUMETSAT-defined names)
    eumetsat_consumer_key: str = Field(..., alias="EUMETSAT_CONSUMER_KEY")
    eumetsat_consumer_secret: str = Field(..., alias="EUMETSAT_CONSUMER_SECRET")

    # Application config (we define these)
    collections: list[str] = Field(default_factory=list, alias="WATCHTOWER_COLLECTIONS")
    @field_validator("collections", mode="before")
    @classmethod
    def _split_collections(cls, v: str | list[str]) -> list[str]:
        """Accept comma-separated strings or proper lists."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v
    poll_interval_seconds: int = Field(default=300, alias="WATCHTOWER_POLL_INTERVAL_SECONDS")
    db_url: str = Field(default="sqlite:///./watchtower.db", alias="WATCHTOWER_DB_URL")
    log_level: str = Field(default="INFO", alias="WATCHTOWER_LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    `lru_cache` ensures we read the environment only once per process,
    not on every call. This is faster and prevents subtle bugs where
    config changes mid-run.
    """
    return Settings()  # type: ignore[call-arg]

