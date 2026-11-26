from datetime import datetime, timedelta

import pytest
from conftest import BEFORE_THE_CLOSE, MakeClient, sign_in
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

SIXTY_DAYS = timedelta(days=60)


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
def signed_in_with_clock(
    clock: Clock, make_client: MakeClient, student: OnTheRoster
) -> TestClient:
    client = make_client(clock=clock)
    sign_in(client, student.github_id)
    return client


def test_a_student_who_comes_back_stays_signed_in_past_sixty_days(
    clock: Clock, signed_in_with_clock: TestClient
) -> None:
    for _ in range(4):
        clock.advance(SIXTY_DAYS * 3 / 4)

        assert signed_in_with_clock.get("/api/me").status_code == 200


def test_a_student_away_longer_than_sixty_days_signs_in_again(
    clock: Clock, signed_in_with_clock: TestClient
) -> None:
    clock.advance(SIXTY_DAYS + timedelta(days=1))

    assert signed_in_with_clock.get("/api/me").status_code == 401


def test_a_restart_keeps_the_student_signed_in(
    clock: Clock, make_client: MakeClient, signed_in_with_clock: TestClient
) -> None:
    restarted = make_client(clock=clock)
    restarted.cookies = signed_in_with_clock.cookies

    assert restarted.get("/api/me").status_code == 200
