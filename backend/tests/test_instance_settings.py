import pytest
from courses_under_test import TWO_GROUP_FIXTURE

from app.main import ConfigurationError, create_app
from app.settings import Settings


def start_with_the_github_store(repository: str = "", store_app_slug: str = "") -> None:
    create_app(
        settings=Settings(
            _env_file=None,
            session_secret="test-secret",
            sign_in="fake",
            course_folder=str(TWO_GROUP_FIXTURE.folder),
            roster_file=str(TWO_GROUP_FIXTURE.roster_file),
            store="github",
            repository=repository,
            store_app_slug=store_app_slug,
        ),
    )


def test_the_github_store_without_a_repository_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_REPOSITORY"):
        start_with_the_github_store(store_app_slug="demo-store")


def test_the_github_store_without_the_store_apps_slug_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_STORE_APP_SLUG"):
        start_with_the_github_store(repository="demo-school/demo-course")
