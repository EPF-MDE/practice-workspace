import pytest
from courses_under_test import TWO_GROUP_FIXTURE

from app.main import create_app
from app.settings import ConfigurationError, Settings


def start(**instance_settings: str) -> None:
    create_app(
        settings=Settings(
            _env_file=None,
            session_secret="test-secret",
            sign_in="fake",
            course_folder=str(TWO_GROUP_FIXTURE.folder),
            roster_file=str(TWO_GROUP_FIXTURE.roster_file),
        ).model_copy(update=instance_settings),
    )


def test_the_github_store_without_a_repository_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_REPOSITORY"):
        start(store="github", store_app_slug="demo-store")


def test_the_github_store_without_the_store_apps_slug_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_STORE_APP_SLUG"):
        start(store="github", repository="demo-school/demo-course")


def test_github_repository_reading_without_a_repository_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_REPOSITORY"):
        start(repository_reading="github")
