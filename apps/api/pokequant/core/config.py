"""Typed application settings (12-factor: all config via env / .env).

See docs/13-engineering-standards.md (Configuration & secrets).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Values come from environment variables (preferred in deployed environments)
    or a local `.env` file. Field names map case-insensitively to env vars.
    """

    model_config = SettingsConfigDict(
        # When invoked from apps/api (make targets) the repo-root .env is two levels up.
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="local", alias="POKEQUANT_ENV")
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "postgresql+psycopg://pokequant:pokequant@localhost:5432/pokequant"
    redis_url: Optional[str] = None

    artifact_dir: Path = Path("./data/artifacts")
    allow_synthetic_in_scoring: bool = False

    cors_origins: str = "http://localhost:3000"

    # Provider credentials - all optional; the pipeline degrades gracefully / uses
    # the synthetic backfill when a source is unavailable (see docs/02-data-sources.md).
    pokemontcg_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    ebay_client_id: Optional[str] = None
    ebay_client_secret: Optional[str] = None
    ebay_marketplace_id: str = "EBAY_US"
    groq_api_key: Optional[str] = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
