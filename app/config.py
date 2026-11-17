from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mastodon_base_url: str = "https://mastodon.social"
    mastodon_access_token: Optional[str] = None
    bluesky_handle: Optional[str] = None
    bluesky_app_password: Optional[str] = None
    devto_api_key: Optional[str] = None
    github_token: Optional[str] = None
    telegraph_access_token: Optional[str] = None
    request_timeout_seconds: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
