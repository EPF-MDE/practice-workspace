from datetime import datetime, timedelta

import pytest
from conftest import BEFORE_THE_CLOSE, sign_in
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

from app.auth import SESSION_IDLE_LIMIT, FakeIdentity
from app.main import create_app
from app.settings import Settings
from app.store import InMemoryStore


class Clock:
    def __init__(self) -> None:
        self._now = BEFORE_THE_CLOSE

    def __call__(self) -> datetime:
        return self._now

    def advance(self, time: timedelta) -> None:
        self._now += time


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def signed_in_on(
    clock: Clock, test_settings: Settings, store: InMemoryStore, student: OnTheRoster
) -> TestClient:
    client = TestClient(
        create_app(
            settings=test_settings,
            identity=FakeIdentity(),
            store=store,
            clock=clock,
        )
    )
    sign_in(client, student.github_id)
    return client


def test_a_student_who_comes_back_stays_signed_in_past_the_idle_limit(
    clock: Clock, signed_in_on: TestClient
) -> None:
    for _ in range(4):
        clock.advance(SESSION_IDLE_LIMIT * 3 / 4)

        assert signed_in_on.get("/api/me").status_code == 200


def test_a_student_away_longer_than_the_idle_limit_signs_in_again(
    clock: Clock, signed_in_on: TestClient
) -> None:
    clock.advance(SESSION_IDLE_LIMIT + timedelta(days=1))

    assert signed_in_on.get("/api/me").status_code == 401
