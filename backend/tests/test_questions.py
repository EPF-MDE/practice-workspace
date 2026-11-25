from datetime import datetime
from typing import Any

from conftest import MakeClient, sign_in
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

from app.settings import Settings

PAGE = "/api/competencies/C1"


def questions_of(page: dict[str, Any], step_id: str) -> list[str]:
    step = next(s for s in page["steps"] if s["id"] == step_id)
    return [q["text"] for q in step["questions"]]


def test_a_question_is_stored_with_its_step(
    client: TestClient, student: OnTheRoster
) -> None:
    sign_in(client, student.github_id)

    response = client.post(
        f"{PAGE}/steps/read-the-chain/questions", json={"text": "Why 10?"}
    )

    assert response.status_code == 200
    page = client.get(PAGE).json()
    assert questions_of(page, "read-the-chain") == ["Why 10?"]
    assert questions_of(page, "guided-calculation") == []


def test_every_question_is_kept(client: TestClient, student: OnTheRoster) -> None:
    sign_in(client, student.github_id)
    client.post(f"{PAGE}/steps/guided-calculation/questions", json={"text": "First"})
    client.post(f"{PAGE}/steps/guided-calculation/questions", json={"text": "Second"})

    assert questions_of(client.get(PAGE).json(), "guided-calculation") == [
        "First",
        "Second",
    ]


def test_a_question_needs_text_and_a_real_step(
    client: TestClient, student: OnTheRoster
) -> None:
    sign_in(client, student.github_id)

    assert (
        client.post(
            f"{PAGE}/steps/read-the-chain/questions", json={"text": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(f"{PAGE}/steps/nowhere/questions", json={"text": "?"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/competencies/C9/steps/x/questions", json={"text": "?"}
        ).status_code
        == 404
    )


def test_a_question_after_the_workspace_closed_is_refused(
    make_client: MakeClient,
    test_settings: Settings,
    past: datetime,
    student: OnTheRoster,
) -> None:
    client = make_client(settings=test_settings.model_copy(update={"closes_at": past}))
    sign_in(client, student.github_id)

    response = client.post(
        f"{PAGE}/steps/read-the-chain/questions", json={"text": "Late?"}
    )

    assert response.status_code == 403
    assert "closed" in response.json()["detail"]


def test_asking_needs_a_signed_in_student(client: TestClient) -> None:
    assert (
        client.post(
            f"{PAGE}/steps/read-the-chain/questions", json={"text": "?"}
        ).status_code
        == 401
    )
