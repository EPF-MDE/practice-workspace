import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

DAY = 60 * 60 * 24


class Days:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._now = time.time()
        monkeypatch.setattr(
            "itsdangerous.timed.time", SimpleNamespace(time=lambda: self._now)
        )

    def pass_(self, days: int) -> None:
        self._now += days * DAY


@pytest.fixture
def days(monkeypatch: pytest.MonkeyPatch) -> Days:
    return Days(monkeypatch)


def test_a_student_who_comes_back_stays_signed_in_past_the_idle_limit(
    days: Days, signed_in: TestClient
) -> None:
    for _ in range(4):
        days.pass_(45)

        assert signed_in.get("/api/me").status_code == 200


def test_a_student_away_longer_than_the_idle_limit_signs_in_again(
    days: Days, signed_in: TestClient
) -> None:
    days.pass_(61)

    assert signed_in.get("/api/me").status_code == 401
