from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Typed runtime settings with environment variable overrides.

    Environment variables introduced (prefix DC_):
    - DC_MAR_BASE_URL
    - DC_MAR_API_BASE_PATH
    - DC_ROBOTS_URL
    - DC_DEFAULT_TIMEOUT
    - DC_DRIFT_USER_AGENT
    - DC_DEFAULT_USER_AGENT
    - DC_DEFAULT_CACHE_TTL
    - DC_SWAGGER_DIR
    - DC_SWAGGER_FILE
    - DC_MAR_API_KEY (used elsewhere by scripts/CLI)
    """

    mar_base_url: str = Field("https://datagate.dc.gov/mar/open")
    mar_api_base_path: str = Field("/api/v2.2")
    robots_url: str = Field("https://opendata.dc.gov/robots.txt")

    default_timeout_seconds: int = Field(30)
    default_cache_ttl_seconds: int = Field(3600)

    # Optional cache policy defaults (when provided they are advisory only and do not
    # change existing behavior unless callers opt into the policy-aware client APIs).
    default_cache_use: bool = Field(True)
    autocomplete_cache_ttl_seconds: Optional[int] = Field(None)
    search_cache_ttl_seconds: Optional[int] = Field(None)

    drift_user_agent: str = Field("dc-mar-sdk-drift-check")
    default_user_agent: str = Field("dc-mar-sdk/0.1")
    mar_api_key: str = Field("")
    telemetry_db_path: Optional[str] = Field(None)

    swagger_dir: str = Field("swagger")
    swagger_file_name: str = Field("swagger.json")

    model_config = SettingsConfigDict(
        env_prefix="DC_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
