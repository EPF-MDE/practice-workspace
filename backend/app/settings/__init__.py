from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPOSITORY_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class ConfigurationError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKSPACE_",
        env_file=_REPOSITORY_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sign_in: Literal["github", "fake"] = "github"
    session_secret: str = ""
    public_url: str = "http://localhost:8000"

    repository: str = ""
    store: Literal["memory", "github"] = "memory"
    store_label: str = "practice"
    data_branch: str = "workspace-data"
    course_folder: str = ""
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

    def require(self, needed_by: str, *names: str) -> None:
        missing = [
            f"WORKSPACE_{name.upper()}" for name in names if not getattr(self, name)
        ]
        if missing:
            raise ConfigurationError(
                f"{needed_by} needs the Instance setting {' and '.join(missing)}"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
