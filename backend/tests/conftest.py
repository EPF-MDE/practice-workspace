from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple, Protocol

import httpx
import pytest
from courses_under_test import EVERY_FIXTURE, CourseFolder, OnTheRoster
from fake_github import FakeGitHub
from fastapi.testclient import TestClient

from app.auth import FakeIdentity, Identity
from app.evidence_panel import (
    AccessCheck,
    FakeAccessCheck,
    OfflineRepositoryReading,
    RepositoryReadingSource,
)
from app.main import create_app
from app.roster import RosterSource
from app.settings import PARIS, Settings
from app.store import GitHubStore, InMemoryStore, Store


@pytest.fixture(params=EVERY_FIXTURE, ids=lambda course: course.label)
def course(request: pytest.FixtureRequest) -> CourseFolder:
    chosen: CourseFolder = request.param
    return chosen


@pytest.fixture
def student(course: CourseFolder) -> OnTheRoster:
    return course.student


@pytest.fixture
def roster_csv(course: CourseFolder) -> str:
    return course.roster_csv


@pytest.fixture
def test_settings(course: CourseFolder) -> Settings:
    return Settings(
        _env_file=None,
        session_secret="test-secret",
        sign_in="fake",
        public_url="http://testserver",
        course_folder=str(course.folder),
        roster_file=str(course.roster_file),
    )


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def past() -> datetime:
    return datetime(2020, 1, 1, tzinfo=PARIS)


@pytest.fixture
def future() -> datetime:
    return datetime(2100, 1, 1, tzinfo=PARIS)


class MakeClient(Protocol):
    def __call__(
        self,
        settings: Settings | None = None,
        roster: RosterSource | None = None,
        identity: Identity | None = None,
        store: Store = ...,
        repository_reading: RepositoryReadingSource | None = None,
        access_check: AccessCheck | None = None,
    ) -> TestClient: ...


@pytest.fixture
def make_client(test_settings: Settings, store: InMemoryStore) -> MakeClient:
    def make(
        settings: Settings | None = None,
        roster: RosterSource | None = None,
        identity: Identity | None = None,
        store: Store = store,
        repository_reading: RepositoryReadingSource | None = None,
        access_check: AccessCheck | None = None,
    ) -> TestClient:
        app = create_app(
            settings=settings or test_settings,
            roster=roster,
            identity=identity or FakeIdentity(),
            store=store,
            repository_reading=repository_reading,
            access_check=access_check,
        )
        return TestClient(app)

    return make


@pytest.fixture
def client(make_client: MakeClient) -> TestClient:
    return make_client()


def sign_in(client: TestClient, github_id: int) -> httpx.Response:
    response: httpx.Response = client.get(
        "/auth/login", params={"github_id": github_id}
    )
    return response


@pytest.fixture
def signed_in(client: TestClient, student: OnTheRoster) -> TestClient:
    sign_in(client, student.github_id)
    return client


class Counted(NamedTuple):
    client: TestClient
    writes: Callable[[], int]


@pytest.fixture(params=["memory", "github"])
def counted(
    request: pytest.FixtureRequest, make_client: MakeClient, student: OnTheRoster
) -> Counted:
    store: Store
    writes: Callable[[], int]
    if request.param == "memory":
        memory = InMemoryStore()
        store, writes = memory, lambda: memory.writes
    else:
        github = FakeGitHub()
        store = GitHubStore(github.client(), github.repository)
        writes = lambda: github.write_requests  # noqa: E731
    client = make_client(
        store=store,
        repository_reading=OfflineRepositoryReading(),
        access_check=FakeAccessCheck(),
    )
    sign_in(client, student.github_id)
    return Counted(client, writes)


def c1_levels(**by_point: str | tuple[str, str]) -> dict[str, Any]:
    rated: dict[str, dict[str, str | None]] = {}
    for letter, value in by_point.items():
        level, link = value if isinstance(value, tuple) else (value, None)
        rated[f"C1.{letter}"] = {"level": level, "link": link}
    return {"levels": rated}
