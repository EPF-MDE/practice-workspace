from pathlib import Path

import pytest
from conftest import ADA_OF_OCEENS, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.settings import Settings

CONTENT = """---
competency: C2
title: Industrialize a service through a CI/CD pipeline
---

## Predict the red {#predict minutes=10}

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
def ada(make_client: MakeClient, test_settings: Settings, tmp_path: Path) -> TestClient:
    (tmp_path / "course.toml").write_text('name = "Choice course"\n')
    (tmp_path / "c2.md").write_text(CONTENT)
    client = make_client(
        settings=test_settings.model_copy(update={"course_folder": str(tmp_path)})
    )
    sign_in(client, ADA_OF_OCEENS)
    return client


def test_the_page_serves_a_choice_field_with_its_options(ada: TestClient) -> None:
    (step,) = ada.get(PAGE).json()["steps"]
    red = next(b for b in step["blocks"] if b["type"] == "field" and b["id"] == "red")

    assert (red["kind"], red["options"]) == ("choice", ["none", "architecture", "test"])


def test_an_option_is_stored_and_releases_the_answer(ada: TestClient) -> None:
    sent = ada.post(ANSWER, json={"fields": {"red": "test", "why": ""}})

    assert sent.status_code == 200
    assert "REFERENCE" in sent.json()["unlocked"][0]
    (step,) = ada.get(PAGE).json()["steps"]
    assert step["sent"]["fields"]["red"] == "test"


def test_a_value_that_is_not_an_option_is_refused(ada: TestClient) -> None:
    refused = ada.post(ANSWER, json={"fields": {"red": "deploy to Mars"}})

    assert refused.status_code == 422
    assert "red" in refused.json()["detail"]
