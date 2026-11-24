from typing import Any

import pytest
from conftest import sign_in
from courses_under_test import DEMO_COURSE, ONE_GROUP_FIXTURE, CourseFolder
from fastapi.testclient import TestClient


@pytest.fixture(
    params=[DEMO_COURSE, ONE_GROUP_FIXTURE], ids=lambda course: course.label
)
def course(request: pytest.FixtureRequest) -> CourseFolder:
    chosen: CourseFolder = request.param
    return chosen


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


def test_the_course_is_served_under_its_name(
    client: TestClient, course: CourseFolder
) -> None:
    assert client.get("/api/course").json()["name"] == course.name


def test_each_groups_student_signs_in_with_their_group(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)

        assert client.get("/api/me").json()["group"] == student.group


def test_each_groups_student_sends_an_answer_and_gets_the_instructors(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)
        step = first_step_with_fields(client.get("/api/competencies/C1").json())

        sent = client.post(
            f"/api/competencies/C1/steps/{step['id']}/answer",
            json={"fields": filled(step)},
        )

        assert sent.status_code == 200
        assert sent.json()["unlocked"]


def test_each_groups_student_has_an_evidence_panel(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)

        assert client.get("/api/competencies/C1/evidence-panel").status_code == 200
