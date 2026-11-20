from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import FakeIdentity, Identity
from app.evidence_panel import AccessCheck, RepositoryReadingSource
from app.main import create_app
from app.roster import RosterSource, StaticRoster, parse_roster
from app.settings import PARIS, Settings
from app.store import InMemoryStore, Store

FIXTURES = Path(__file__).parent / "fixtures"

Counted = tuple[TestClient, Callable[[], int]]

ADA = 1001
GRACE = 1002


@pytest.fixture
def roster_csv() -> str:
    return (FIXTURES / "roster.csv").read_text(encoding="utf-8")


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        session_secret="test-secret",
        sign_in="fake",
        public_url="http://testserver",
        content_dir=str(FIXTURES / "content"),
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
def make_client(
    roster_csv: str, test_settings: Settings, store: InMemoryStore
) -> MakeClient:
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
            roster=roster or StaticRoster(parse_roster(roster_csv)),
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
