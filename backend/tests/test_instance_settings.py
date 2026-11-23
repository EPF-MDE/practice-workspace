from collections.abc import Callable

import pytest

from app.main import create_app
from app.settings import ConfigurationError, Settings

Start = Callable[..., None]


@pytest.fixture
def start(test_settings: Settings) -> Start:
    def started(**instance_settings: str) -> None:
        create_app(settings=test_settings.model_copy(update=instance_settings))

    return started


def test_the_github_store_without_a_repository_refuses_to_start(start: Start) -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_REPOSITORY"):
        start(store="github", store_app_slug="demo-store")


def test_the_github_store_without_the_store_apps_slug_refuses_to_start(
    start: Start,
) -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_STORE_APP_SLUG"):
        start(store="github", repository="demo-school/demo-course")


def test_github_repository_reading_without_a_repository_refuses_to_start(
    start: Start,
) -> None:
    with pytest.raises(ConfigurationError, match="WORKSPACE_REPOSITORY"):
        start(repository_reading="github")
