import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import ADA_OF_OCEENS, FIXTURES, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.main import ConfigurationError
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]
THREE_LEVELS = FIXTURES / "courses" / "three-levels"
PAGE = "/api/competencies/C1"
SELF = f"{PAGE}/self-assessment"
DRAFT = f"{PAGE}/evidence-plan/draft"
LINK = "https://github.com/ada/notes/pull/4"
SETTINGS = 'name = "A course"\n\n'
TWO_LEVELS = (
    SETTINGS
    + '[[levels]]\nid = "started"\nlabel = "Started"\n\n'
    + '[[levels]]\nid = "finished"\nlabel = "Finished"\n'
)
CLOSING_WITH = (
    "---\ncompetency: C1\ntitle: T\n---\n\n"
    "## Close C1 {{#closing minutes=0 kind=closing}}\n\n"
    "::: point {{#C1.a band=Basic}}\nA statement.\n\n"
    "::: to-get-there {{level={level}}}\nA way there.\n:::\n:::\n"
)


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
    closes_at: datetime,
    reading_day_at: datetime,
) -> TestClient:
    client = make_client(
        settings=test_settings.model_copy(
            update={
                "course_folder": str(THREE_LEVELS),
                "closes_at": closes_at,
                "reading_day_at": reading_day_at,
            }
        )
    )
    sign_in(client, ADA_OF_OCEENS)
    return client


@pytest.fixture
def ada(
    make_client: MakeClient, test_settings: Settings, future: datetime
) -> TestClient:
    return on_three_levels(make_client, test_settings, future, future)


def verify(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app", "verify", str(folder)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


def a_course(folder: Path, settings: str, to_get_there: str) -> Path:
    (folder / "course.toml").write_text(settings)
    (folder / "c1.md").write_text(CLOSING_WITH.format(level=to_get_there))
    return folder


def test_the_api_serves_the_courses_scale_in_order(ada: TestClient) -> None:
    assert ada.get("/api/course").json()["scale"] == [
        {"id": "seen", "label": "Seen it"},
        {"id": "tried", "label": "Tried it"},
        {"id": "shipped", "label": "Shipped it"},
    ]


def test_the_evidence_plan_is_drafted_for_exactly_the_points_below_the_top_level(
    ada: TestClient,
) -> None:
    text = ada.post(DRAFT, json=rated(a="seen", b="tried", c=("shipped", LINK))).json()[
        "text"
    ]

    seen, tried = blocks(text)
    assert seen.startswith("C1.a (Basic), Seen it")
    assert "To get there: SEEN-TO-GET-THERE" in seen
    assert tried.startswith("C1.b (Solid), Tried it")
    assert "To get there: TRIED-TO-GET-THERE" in tried
    assert "C1.c" not in text


def test_the_top_level_needs_a_link_and_a_level_of_another_scale_is_refused(
    ada: TestClient,
) -> None:
    without_link = ada.post(SELF, json=rated(c="shipped"))
    another_scale = ada.post(SELF, json=rated(a="understand"))

    assert without_link.status_code == 422
    assert "Shipped it" in without_link.json()["detail"]
    assert another_scale.status_code == 422
    assert "Seen it, Tried it, Shipped it" in another_scale.json()["detail"]


def test_after_the_close_a_point_only_moves_up_to_the_top_level(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = on_three_levels(make_client, test_settings, future, future)
    before.post(SELF, json=rated(a="seen", b="tried"))
    after = on_three_levels(make_client, test_settings, past, future)

    down = after.post(SELF, json=rated(a="seen", b="seen"))
    up = after.post(SELF, json=rated(a=("shipped", LINK), b="tried"))

    assert down.status_code == 403
    assert '"Shipped it"' in down.json()["detail"]
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
    result = verify(a_course(tmp_path, SETTINGS + "levels = []\n", "started"))

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
    folder = a_course(tmp_path, SETTINGS + "levels = []\n", "started")

    with pytest.raises(ConfigurationError, match="no Self-assessment level"):
        make_client(
            settings=test_settings.model_copy(update={"course_folder": str(folder)})
        )


def test_a_stored_level_the_scale_no_longer_holds_still_serves_the_page(
    make_client: MakeClient, test_settings: Settings, future: datetime, tmp_path: Path
) -> None:
    ada = on_three_levels(make_client, test_settings, future, future)
    ada.post(SELF, json=rated(a="seen", b="tried"))
    for name in ("course.toml", "c1.md"):
        text = (THREE_LEVELS / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text.replace("seen", "glimpsed"))
    renamed = make_client(
        settings=test_settings.model_copy(
            update={"course_folder": str(tmp_path), "closes_at": future}
        )
    )
    sign_in(renamed, ADA_OF_OCEENS)

    page = renamed.get(PAGE)

    assert page.status_code == 200
    assert page.json()["evidence_plan_draft"].startswith("C1.a (Basic), seen")
