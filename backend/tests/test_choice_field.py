from pathlib import Path

import pytest
from conftest import MakeClient, sign_in
from course_folders import with_every_competency, write_course_folder
from courses_under_test import TWO_GROUP_FIXTURE, CourseFolder
from fastapi.testclient import TestClient

from app.settings import Settings

CONTENT = """## Predict the red {#predict minutes=10}

::: field {#red kind=choice options="none|architecture|test"}
Which job goes red?
:::

::: field {#why kind=line}
Why?
:::

::: answer
REFERENCE: `test` goes red.
:::
"""
PAGE = "/api/competencies/C2"
ANSWER = f"{PAGE}/steps/predict/answer"


@pytest.fixture
def course() -> CourseFolder:
    return TWO_GROUP_FIXTURE


@pytest.fixture
def signed_in(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> TestClient:
    write_course_folder(tmp_path, with_every_competency(C2=CONTENT))
    client = make_client(
        settings=test_settings.model_copy(update={"course_folder": str(tmp_path)})
    )
    sign_in(client, TWO_GROUP_FIXTURE.student.github_id)
    return client


def test_the_page_serves_a_choice_field_with_its_options(signed_in: TestClient) -> None:
    (step,) = signed_in.get(PAGE).json()["steps"]
    red = next(b for b in step["blocks"] if b["type"] == "field" and b["id"] == "red")

    assert (red["kind"], red["options"]) == ("choice", ["none", "architecture", "test"])


def test_an_option_is_stored_and_releases_the_answer(signed_in: TestClient) -> None:
    sent = signed_in.post(ANSWER, json={"fields": {"red": "test", "why": ""}})

    assert sent.status_code == 200
    assert "REFERENCE" in sent.json()["unlocked"][0]
    (step,) = signed_in.get(PAGE).json()["steps"]
    assert step["sent"]["fields"]["red"] == "test"


def test_a_value_that_is_not_an_option_is_refused(signed_in: TestClient) -> None:
    refused = signed_in.post(ANSWER, json={"fields": {"red": "deploy to Mars"}})

    assert refused.status_code == 422
    assert "red" in refused.json()["detail"]
