from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PARIS = ZoneInfo("Europe/Paris")

_REPOSITORY_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKSPACE_",
        env_file=_REPOSITORY_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    closes_at: datetime = datetime(2026, 12, 14, 23, 59, tzinfo=PARIS)
    reading_day_at: datetime = datetime(2027, 1, 4, 23, 59, tzinfo=PARIS)

    sign_in: Literal["github", "fake"] = "github"
    session_secret: str = ""
    public_url: str = "http://localhost:8000"

    repository: str = "EPF-MDE/complex-web-services"
    store: Literal["memory", "github"] = "memory"
    store_label: str = "practice"
    data_branch: str = "workspace-data"
    content_dir: str = ""
    roster_file: str = ""
    repository_reading: Literal["auto", "fake", "github"] = "auto"
    repository_readings_dir: str = ""

    github_app_id: str = ""
    github_app_slug: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_private_key_base64: str = ""
    github_app_installation_id: str = ""

    store_app_id: str = ""
    store_app_slug: str = ""
    store_app_client_id: str = ""
    store_app_client_secret: str = ""
    store_app_private_key_base64: str = ""
    store_app_installation_id: str = ""

    tldraw_license_key: str = ""

    posthog_project_token: str = ""
    posthog_host: str = ""
    posthog_environment: str = ""
    error_check_key: str = ""

    @field_validator("closes_at", "reading_day_at")
    @classmethod
    def _in_paris_unless_told(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=PARIS)


@lru_cache
def get_settings() -> Settings:
    return Settings()
