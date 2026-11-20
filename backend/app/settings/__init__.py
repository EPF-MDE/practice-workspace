"""The app's settings, read from the environment.

The fast-questionnaire pattern: nothing is committed. Locally they come from
the gitignored `.env` at the root of this repository (an environment variable
already set wins over it); on Azure, from each app's App settings.
Every name starts with `WORKSPACE_`, e.g. `WORKSPACE_CLOSES_AT`.

The cut-off dates are settings, not constants (#460): tests move them into the
past or the future, and the Instructor can move them without a deploy.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PARIS = ZoneInfo("Europe/Paris")

# backend/app/settings/__init__.py -> the repository's root.
_REPOSITORY_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKSPACE_",
        env_file=_REPOSITORY_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The workspace closes: after it, a point not rated yet takes its first level
    # freely, and a level already given only moves up to "I have done it".
    closes_at: datetime = datetime(2026, 12, 14, 23, 59, tzinfo=PARIS)
    # The Reading Day: after it, nothing changes.
    reading_day_at: datetime = datetime(2027, 1, 4, 23, 59, tzinfo=PARIS)

    # "github" in every deployed app; "fake" only for tests and the local
    # Playwright path, and refused on Azure (see app.main).
    sign_in: Literal["github", "fake"] = "github"
    # Signs the session cookie. Required when deployed.
    session_secret: str = ""
    # The address the Student's browser uses, for GitHub's callback.
    public_url: str = "http://localhost:8000"

    # Where the Store and the roster live.
    repository: str = "EPF-MDE/complex-web-services"
    # Which Store keeps the sends: "memory" (tests, local runs; lost on restart)
    # or "github" (one issue per Student on `repository`, as the Store App).
    store: Literal["memory", "github"] = "memory"
    # The label of the Students' issues: "rehearsal"; staging uses its own, so
    # the Instructor's tests on staging never mix with the Students' issues.
    store_label: str = "rehearsal"
    data_branch: str = "workspace-data"
    # The content files (c1.md...): the artefact's `content/`. No default course:
    # without it (or the artefact's folder), the app refuses to start.
    content_dir: str = ""
    # A local roster file instead of `roster.csv` on the data branch (local runs).
    roster_file: str = ""
    # Where the fork panel's readings come from: "github" (the fork reading, with the
    # Student Connector, stored on `data_branch`) or "fake" (no GitHub: readings from
    # `fork_readings_dir`, else an empty fork). "auto": fake with the fake sign-in,
    # github otherwise.
    fork_reading: Literal["auto", "fake", "github"] = "auto"
    # The fake's readings, one `fork-readings/<login>.json` each; empty: the test
    # fixtures' folder.
    fork_readings_dir: str = ""

    # EPF-MDE CWS Student Connector: "Sign in with GitHub", read-only on forks.
    github_app_id: str = ""
    github_app_slug: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_private_key_base64: str = ""
    # The Student Connector's installation the fork reading reads with; empty: its first
    # installation.
    github_app_installation_id: str = ""

    # EPF-MDE CWS Store: Issues and Contents write on this repository alone.
    store_app_id: str = ""
    store_app_slug: str = ""
    store_app_client_id: str = ""
    store_app_client_secret: str = ""
    store_app_private_key_base64: str = ""
    store_app_installation_id: str = ""

    # tldraw's hobby licence, for cws-workspace-production's domain only.
    tldraw_license_key: str = ""

    # Errors and logs, to the Instructor's own PostHog project. All three or none.
    posthog_project_token: str = ""
    posthog_host: str = ""
    posthog_environment: str = ""
    # Opens GET /api/health/error?key=..., which raises on purpose so the
    # Instructor can see an error reach PostHog. Empty: the route answers 404.
    error_check_key: str = ""

    @field_validator("closes_at", "reading_day_at")
    @classmethod
    def _in_paris_unless_told(cls, value: datetime) -> datetime:
        """A date set without an offset is Paris time, as the course states it."""
        return value if value.tzinfo else value.replace(tzinfo=PARIS)


@lru_cache
def get_settings() -> Settings:
    """The settings of the running app, read once."""
    return Settings()
