import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import AFTER_THE_CLOSE, BEFORE_THE_CLOSE, MakeClient, sign_in
from course_folders import CALENDAR, ONE_STEP, TWO_GROUPS, front_matter
from courses_under_test import FIXTURES, TWO_GROUP_FIXTURE, CourseFolder
from fastapi.testclient import TestClient

from app.course import COMPETENCIES
from app.settings import ConfigurationError, Settings

BACKEND = Path(__file__).resolve().parents[1]
THREE_LEVELS = FIXTURES / "courses" / "three-levels"
PAGE = "/api/competencies/C1"
SELF = f"{PAGE}/self-assessment"
DRAFT = f"{PAGE}/evidence-plan/draft"
LINK = "https://github.com/ada/notes/pull/4"
NAME = 'name = "A course"\nread_when_none_declared = "roster"\n'
TITLES = "".join(
    f'\n[competencies.{c}]\ntitle = "{c}"\nminutes = 40\n' for c in COMPETENCIES
)
SETTINGS = NAME + TWO_GROUPS + TITLES + CALENDAR
NO_LEVEL = NAME + "levels = []\n" + TWO_GROUPS + TITLES + CALENDAR
TWO_LEVELS = (
    SETTINGS
    + '\n[[levels]]\nid = "started"\nlabel = "Started"\n\n'
    + '[[levels]]\nid = "finished"\nlabel = "Finished"\n'
)
CLOSING_WITH = (
    "---\ncompetency: C1\n---\n\n"
    "## Close C1 {{#closing minutes=0 kind=closing}}\n\n"
    "::: point {{#C1.a band=Basic}}\nA statement.\n\n"
    "::: to-get-there {{level={level}}}\nA way there.\n:::\n:::\n"
)


@pytest.fixture
def course() -> CourseFolder:
    return TWO_GROUP_FIXTURE


def rated(**by_point: str | tuple[str, str]) -> dict[str, Any]:
    levels: dict[str, dict[str, str | None]] = {}
    for letter, value in by_point.items():
        level, link = value if isinstance(value, tuple) else (value, None)
        levels[f"C1.{letter}"] = {"level": level, "link": link}
    return {"levels": levels}


def blocks(text: str) -> list[str]:
    return [b for b in text.split("\n\n") if b.strip()]


def on_three_levels(
    make_client: MakeClient,
    test_settings: Settings,
    now: datetime,
) -> TestClient:
    client = make_client(
        settings=test_settings.model_copy(update={"course_folder": str(THREE_LEVELS)}),
        now=now,
    )
    sign_in(client, TWO_GROUP_FIXTURE.student.github_id)
    return client


@pytest.fixture
def signed_in(make_client: MakeClient, test_settings: Settings) -> TestClient:
    return on_three_levels(make_client, test_settings, BEFORE_THE_CLOSE)


def verify(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app", "verify", str(folder)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


def a_course(folder: Path, settings: str, to_get_there: str) -> Path:
    (folder / "course.toml").write_text(settings, encoding="utf-8")
    (folder / "c1.md").write_text(CLOSING_WITH.format(level=to_get_there))
    for competency in COMPETENCIES[1:]:
        (folder / f"{competency.lower()}.md").write_text(
            front_matter(competency) + ONE_STEP
        )
    return folder


def test_the_api_serves_the_courses_scale_in_order(signed_in: TestClient) -> None:
    assert signed_in.get("/api/course").json()["scale"] == [
        {"id": "seen", "label": "Seen it"},
        {"id": "tried", "label": "Tried it"},
        {"id": "shipped", "label": "Shipped it"},
    ]


def test_the_evidence_plan_is_drafted_for_exactly_the_points_below_the_top_level(
    signed_in: TestClient,
) -> None:
    text = signed_in.post(
        DRAFT, json=rated(a="seen", b="tried", c=("shipped", LINK))
    ).json()["text"]

    seen, tried = blocks(text)
    assert seen.startswith("C1.a (Basic), Seen it")
    assert "To get there: SEEN-TO-GET-THERE" in seen
    assert tried.startswith("C1.b (Solid), Tried it")
    assert "To get there: TRIED-TO-GET-THERE" in tried
    assert "C1.c" not in text


def test_the_top_level_needs_a_link_and_a_level_of_another_scale_is_refused(
    signed_in: TestClient,
) -> None:
    without_link = signed_in.post(SELF, json=rated(c="shipped"))
    another_scale = signed_in.post(SELF, json=rated(a="understand"))

    assert without_link.status_code == 422
    assert "Shipped it" in without_link.json()["detail"]
    assert another_scale.status_code == 422
    assert "Seen it, Tried it, Shipped it" in another_scale.json()["detail"]


def test_after_the_close_a_point_only_moves_up_to_the_top_level(
    make_client: MakeClient, test_settings: Settings
) -> None:
    before = on_three_levels(make_client, test_settings, BEFORE_THE_CLOSE)
    before.post(SELF, json=rated(a="seen", b="tried"))
    after = on_three_levels(make_client, test_settings, AFTER_THE_CLOSE)

    down = after.post(SELF, json=rated(a="seen", b="seen"))
    short_of_the_top = after.post(SELF, json=rated(a="tried", b="tried"))
    up = after.post(SELF, json=rated(a=("shipped", LINK), b="tried"))

    assert down.status_code == 403
    assert '"Shipped it"' in down.json()["detail"]
    assert short_of_the_top.status_code == 403
    assert up.status_code == 200
    mine = after.get(PAGE).json()["self_assessment"]["levels"]
    assert (mine["C1.a"]["level"], mine["C1.b"]["level"]) == ("shipped", "tried")


@pytest.mark.parametrize(
    "to_get_there", ["understand", "finished"], ids=["unknown level", "top level"]
)
def test_verify_reports_a_to_get_there_level_that_is_not_below_the_top(
    tmp_path: Path, to_get_there: str
) -> None:
    result = verify(a_course(tmp_path, TWO_LEVELS, to_get_there))

    assert result.returncode != 0
    assert f"level={to_get_there}" in result.stdout
    assert "c1.md" in result.stdout


def test_verify_passes_a_to_get_there_level_below_the_top(tmp_path: Path) -> None:
    result = verify(a_course(tmp_path, TWO_LEVELS, "started"))

    assert result.returncode == 0, result.stdout


def test_verify_reports_an_empty_level_list(tmp_path: Path) -> None:
    result = verify(a_course(tmp_path, NO_LEVEL, "started"))

    assert result.returncode != 0
    assert "'levels'" in result.stdout
    assert "no Self-assessment level" in result.stdout


def test_verify_reports_two_levels_sharing_an_id(tmp_path: Path) -> None:
    twice = TWO_LEVELS + '\n[[levels]]\nid = "started"\nlabel = "Again"\n'

    result = verify(a_course(tmp_path, twice, "started"))

    assert result.returncode != 0
    assert "two Self-assessment levels share an id" in result.stdout


def test_the_app_refuses_to_start_on_an_empty_level_list(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    folder = a_course(tmp_path, NO_LEVEL, "started")

    with pytest.raises(ConfigurationError, match="no Self-assessment level"):
        make_client(
            settings=test_settings.model_copy(update={"course_folder": str(folder)})
        )


def test_a_stored_level_the_scale_no_longer_holds_still_serves_the_page(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    signed_in = on_three_levels(make_client, test_settings, BEFORE_THE_CLOSE)
    signed_in.post(SELF, json=rated(a="seen", b="tried"))
    for name in ("course.toml", "c1.md", "c2.md", "c3.md"):
        text = (THREE_LEVELS / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text.replace("seen", "glimpsed"))
    renamed = make_client(
        settings=test_settings.model_copy(update={"course_folder": str(tmp_path)})
    )
    sign_in(renamed, TWO_GROUP_FIXTURE.student.github_id)

    page = renamed.get(PAGE)

    assert page.status_code == 200
    assert page.json()["evidence_plan_draft"].startswith("C1.a (Basic), seen")
