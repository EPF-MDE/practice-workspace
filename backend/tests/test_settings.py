"""The cut-off dates are settings: Paris time unless an offset is given."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.settings import Settings

PARIS = ZoneInfo("Europe/Paris")


def test_the_workspace_closes_on_14_december_and_the_reading_day_is_4_january(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKSPACE_CLOSES_AT", raising=False)
    monkeypatch.delenv("WORKSPACE_READING_DAY_AT", raising=False)
    settings = Settings(_env_file=None)

    assert settings.closes_at == datetime(2026, 12, 14, 23, 59, tzinfo=PARIS)
    assert settings.reading_day_at == datetime(2027, 1, 4, 23, 59, tzinfo=PARIS)


def test_a_cut_off_set_in_the_environment_without_an_offset_is_paris_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_CLOSES_AT", "2026-12-15T08:00")

    settings = Settings(_env_file=None)

    assert settings.closes_at.isoformat() == "2026-12-15T08:00:00+01:00"
