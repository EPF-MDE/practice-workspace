from datetime import datetime
from typing import Any

from conftest import AFTER_THE_CLOSE, FIXTURE_CLOSE, MakeClient, sign_in
from courses_under_test import CourseFolder, OnTheRoster, on_the_two_group_fixture
from fastapi.testclient import TestClient

from app.store import InMemoryStore

PAGE = "/api/competencies/C1"
ANSWER = "/api/competencies/C1/steps/guided-calculation/answer"


def step(page: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(s for s in page["steps"] if s["id"] == step_id)


def blocks(page: dict[str, Any], step_id: str, kind: str) -> list[dict[str, Any]]:
    return [b for b in step(page, step_id)["blocks"] if b["type"] == kind]


def test_the_page_needs_a_signed_in_student(client: TestClient) -> None:
    assert client.get(PAGE).status_code == 401


def test_an_unknown_competency_is_not_found(signed_in: TestClient) -> None:
    assert signed_in.get("/api/competencies/C9").status_code == 404


def test_the_page_lists_the_steps_with_their_timings(signed_in: TestClient) -> None:
    page = signed_in.get(PAGE).json()

    assert page["competency"] == "C1"
    assert [(s["id"], s["minutes"]) for s in page["steps"]] == [
        ("read-the-chain", 10),
        ("guided-calculation", 10),
        ("redraw", 10),
        ("the-number-changes", 5),
        ("redraw-more", 0),
        ("transfer", 5),
        ("closing", 0),
    ]
    assert step(page, "read-the-chain")["kind"] == "read"
    assert step(page, "guided-calculation")["kind"] == "answer"
    assert step(page, "redraw")["kind"] == "drawing"


def test_a_student_receives_their_groups_content_only(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)
        page = client.get(PAGE).text

        assert student.marked("ONLY") in page
        for other in course.others_marked(student, "ONLY"):
            assert other not in page


def test_the_fields_of_a_step_come_with_their_labels(signed_in: TestClient) -> None:
    fields = blocks(signed_in.get(PAGE).json(), "guided-calculation", "field")

    assert [(f["id"], f["kind"]) for f in fields] == [
        ("sentence", "line"),
        ("step-1", "text"),
    ]
    assert "is at most" in fields[0]["label_html"]


def test_every_answer_block_is_locked_before_the_students_answer(
    signed_in: TestClient, course: CourseFolder
) -> None:
    response = signed_in.get(PAGE)
    page = response.json()

    assert blocks(page, "guided-calculation", "answer") == [
        {"type": "answer", "locked": True, "html": None}
    ]
    assert blocks(page, "the-number-changes", "answer") == [
        {"type": "answer", "locked": True, "html": None}
    ]
    every_group = [s.marked("ANSWER") for s in course.one_per_group]
    for withheld in [*every_group, "CHANGES-ANSWER"]:
        assert withheld not in response.text


def test_sending_an_answer_returns_the_block_it_unlocks(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    response = signed_in.post(
        ANSWER,
        json={
            "fields": {"sentence": "10 summaries is at most 2 hours", "step-1": "10"}
        },
    )

    assert response.status_code == 200
    sent = response.json()
    assert sent["version"] == 1
    assert (
        len(sent["unlocked"]) == 1 and student.marked("ANSWER") in sent["unlocked"][0]
    )
    assert "CHANGES-ANSWER" not in response.text


def test_once_sent_the_page_shows_the_answer_and_what_the_student_sent(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    signed_in.post(
        ANSWER, json={"fields": {"sentence": "my sentence", "step-1": "my step"}}
    )

    page = signed_in.get(PAGE).json()

    [answer] = blocks(page, "guided-calculation", "answer")
    assert answer["locked"] is False and student.marked("ANSWER") in answer["html"]
    assert step(page, "guided-calculation")["sent"]["fields"] == {
        "sentence": "my sentence",
        "step-1": "my step",
    }
    assert blocks(page, "the-number-changes", "answer")[0]["locked"] is True


def test_sending_again_stores_a_new_version_and_keeps_every_version(
    signed_in: TestClient,
) -> None:
    signed_in.post(ANSWER, json={"fields": {"sentence": "first"}})
    second = signed_in.post(ANSWER, json={"fields": {"sentence": "second"}}).json()

    assert second["version"] == 2
    sent = step(signed_in.get(PAGE).json(), "guided-calculation")["sent"]
    assert sent["fields"] == {"sentence": "second"}
    assert sent["version"] == 2
    assert [v["fields"]["sentence"] for v in sent["history"]] == ["first", "second"]


def test_one_students_answer_unlocks_nothing_for_another(
    client: TestClient, course: CourseFolder
) -> None:
    sign_in(client, course.student.github_id)
    client.post(ANSWER, json={"fields": {"sentence": "mine"}})

    sign_in(client, course.another.github_id)
    response = client.get(PAGE)

    assert blocks(response.json(), "guided-calculation", "answer")[0]["locked"] is True
    assert course.another.marked("ANSWER") not in response.text


def test_an_answer_names_only_the_steps_fields(signed_in: TestClient) -> None:
    assert signed_in.post(ANSWER, json={"fields": {"nope": "x"}}).status_code == 422, (
        "a field no step has"
    )
    assert (
        signed_in.post(ANSWER, json={"fields": {"sentence": "  "}}).status_code == 422
    ), "a blank field"
    assert (
        signed_in.post(
            "/api/competencies/C1/steps/read-the-chain/answer",
            json={"fields": {"sentence": "x"}},
        ).status_code
        == 422
    ), "a field of another step"
    assert (
        signed_in.post(
            "/api/competencies/C1/steps/nowhere/answer", json={"fields": {"x": "y"}}
        ).status_code
        == 404
    ), "a step that does not exist"


@on_the_two_group_fixture
def test_on_two_groups_a_field_of_the_other_groups_block_is_not_one_of_the_students(
    client: TestClient, course: CourseFolder
) -> None:
    sign_in(client, course.another.github_id)

    sent = client.post(ANSWER, json={"fields": {"sentence": "x", "step-1": "y"}})

    assert sent.status_code == 422


def test_no_response_contains_instructor_notes(signed_in: TestClient) -> None:
    responses = [signed_in.get(PAGE)]
    responses.append(
        signed_in.post(ANSWER, json={"fields": {"sentence": "x", "step-1": "y"}})
    )
    responses.append(signed_in.get(PAGE))

    for response in responses:
        assert "SECRET-COMMENT" not in response.text
        assert "SECRET-INSTRUCTOR-NOTE" not in response.text


def test_links_to_the_instructors_material_are_links(signed_in: TestClient) -> None:
    page = signed_in.get(PAGE).json()

    [reading] = blocks(page, "read-the-chain", "markdown")
    assert '<a href="https://github.com/EPF-MDE/OceENS/issues/105"' in reading["html"]


def test_nothing_is_written_before_a_send(
    signed_in: TestClient, store: InMemoryStore
) -> None:
    client = signed_in
    client.get(PAGE)
    client.get(PAGE)

    assert store.writes == 0

    client.post(ANSWER, json={"fields": {"sentence": "x"}})
    assert store.writes == 1


def test_an_answer_after_the_workspace_closed_is_refused(
    make_client: MakeClient,
    student: OnTheRoster,
) -> None:
    client = make_client(now=AFTER_THE_CLOSE)
    sign_in(client, student.github_id)

    response = client.post(ANSWER, json={"fields": {"sentence": "late"}})

    assert response.status_code == 403
    assert "closed" in response.json()["detail"]
    assert client.get(PAGE).json()["closed"] is True
    assert step(client.get(PAGE).json(), "guided-calculation")["sent"] is None


def test_the_page_says_when_the_workspace_closes(signed_in: TestClient) -> None:
    page = signed_in.get(PAGE).json()

    assert page["closed"] is False
    assert datetime.fromisoformat(page["closes_at"]) == FIXTURE_CLOSE
