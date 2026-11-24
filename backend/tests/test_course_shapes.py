from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURES, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.settings import Settings

DEMO_COURSE = Path(__file__).resolve().parents[2] / "demo-course"
ONE_GROUP = FIXTURES / "courses" / "one-group"


@dataclass(frozen=True)
class Shape:
    folder: Path
    name: str
    students_by_group: dict[str, int]


SHAPES = [
    pytest.param(
        Shape(DEMO_COURSE, "Demo course", {"OcéENS": 1001, "MATHutrice": 1002}),
        id="the two-Group Demo course",
    ),
    pytest.param(
        Shape(ONE_GROUP, "One-Group course", {"Lighthouse": 4001}),
        id="a one-Group Course",
    ),
]


@pytest.fixture(params=SHAPES)
def shape(request: pytest.FixtureRequest) -> Shape:
    chosen: Shape = request.param
    return chosen


@pytest.fixture
def client(
    make_client: MakeClient, test_settings: Settings, shape: Shape
) -> TestClient:
    return make_client(
        settings=test_settings.model_copy(
            update={
                "course_folder": str(shape.folder),
                "roster_file": str(shape.folder / "roster.csv"),
            }
        )
    )


def first_step_with_fields(page: dict[str, Any]) -> dict[str, Any]:
    return next(
        step
        for step in page["steps"]
        if step["kind"] == "answer"
        and not step.get("after")
        and any(b["type"] == "field" for b in step["blocks"])
    )


def filled(step: dict[str, Any]) -> dict[str, str]:
    return {
        b["id"]: (b["options"][0] if b["kind"] == "choice" else "x")
        for b in step["blocks"]
        if b["type"] == "field"
    }


def test_the_course_is_served_under_its_name(client: TestClient, shape: Shape) -> None:
    assert client.get("/api/course").json()["name"] == shape.name


def test_each_groups_student_signs_in_with_their_group(
    client: TestClient, shape: Shape
) -> None:
    for group, github_id in shape.students_by_group.items():
        sign_in(client, github_id)

        assert client.get("/api/me").json()["group"] == group


def test_each_groups_student_sends_an_answer_and_gets_the_instructors(
    client: TestClient, shape: Shape
) -> None:
    for github_id in shape.students_by_group.values():
        sign_in(client, github_id)
        step = first_step_with_fields(client.get("/api/competencies/C1").json())

        sent = client.post(
            f"/api/competencies/C1/steps/{step['id']}/answer",
            json={"fields": filled(step)},
        )

        assert sent.status_code == 200
        assert sent.json()["unlocked"]


def test_each_groups_student_has_an_evidence_panel(
    client: TestClient, shape: Shape
) -> None:
    for github_id in shape.students_by_group.values():
        sign_in(client, github_id)

        assert client.get("/api/competencies/C1/evidence-panel").status_code == 200


@pytest.mark.parametrize("shape", [SHAPES[1]], indirect=True)
def test_a_one_group_course_serves_its_groups_block(client: TestClient) -> None:
    sign_in(client, 4001)
    page = client.get("/api/competencies/C1").json()

    step = next(s for s in page["steps"] if s["id"] == "size-the-lamp")
    assert "LIGHTHOUSE-ONLY" in step["blocks"][0]["html"]
