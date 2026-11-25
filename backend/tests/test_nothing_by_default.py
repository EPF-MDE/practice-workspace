from pathlib import Path

import pytest
from conftest import MakeClient, c1_levels, sign_in
from course_folders import with_every_competency, write_course_folder
from courses_under_test import (
    NOTHING_BY_DEFAULT_FIXTURE,
    ONE_GROUP_FIXTURE,
    CourseFolder,
)
from fastapi.testclient import TestClient
from test_course_folder import on, verify
from test_evidence_project_reading import CountedReading

from app.evidence_panel import FakeAccessCheck
from app.settings import ConfigurationError, Settings

DECLARATION = "/api/evidence-project/declaration"
ORCHARD = {
    "url": "https://github.com/iris/orchard",
    "what_to_read": "The pipeline in .github/workflows.",
}


@pytest.fixture
def course() -> CourseFolder:
    return NOTHING_BY_DEFAULT_FIXTURE


@pytest.fixture
def readings() -> CountedReading:
    return CountedReading()


@pytest.fixture
def signed_in(make_client: MakeClient, readings: CountedReading) -> TestClient:
    client = make_client(repository_reading=readings, access_check=FakeAccessCheck())
    sign_in(client, NOTHING_BY_DEFAULT_FIXTURE.student.github_id)
    return client


def test_the_course_says_it_reads_nothing_by_default(signed_in: TestClient) -> None:
    assert signed_in.get("/api/course").json()["read_when_none_declared"] == "nothing"


def test_a_student_who_declared_nothing_is_asked_to_and_nothing_is_read(
    signed_in: TestClient, readings: CountedReading
) -> None:
    for competency in ("C1", "C2", "C3"):
        panel = signed_in.get(f"/api/competencies/{competency}/evidence-panel")

        assert panel.status_code == 200
        assert panel.json()["evidence_project"] is None
        assert panel.json()["facts"] == []
        assert "not declared your Evidence Project" in panel.json()["unavailable"]
    assert readings.asked == []


def test_once_declared_their_evidence_project_is_read(
    signed_in: TestClient, readings: CountedReading
) -> None:
    assert signed_in.post(DECLARATION, json=ORCHARD).status_code == 200

    panel = signed_in.get("/api/competencies/C1/evidence-panel").json()

    assert panel["evidence_project"] == "iris/orchard"
    assert panel["unavailable"] is None
    assert readings.asked == ["iris/orchard"]


def test_once_withdrawn_nothing_is_read_again(
    signed_in: TestClient, readings: CountedReading
) -> None:
    signed_in.post(DECLARATION, json=ORCHARD)
    signed_in.delete(DECLARATION)

    panel = signed_in.get("/api/competencies/C1/evidence-panel").json()

    assert panel["evidence_project"] is None
    assert readings.asked == []


def test_closing_without_a_declaration_reads_nothing_and_closing_with_one_reads_it(
    signed_in: TestClient, readings: CountedReading
) -> None:
    signed_in.post("/api/competencies/C1/self-assessment", json=c1_levels(a="not-yet"))

    closed = signed_in.post(
        "/api/competencies/C1/close", json={"text": "p", "example": "e"}
    )

    assert closed.status_code == 200
    assert readings.asked == []

    closed = signed_in.post(
        "/api/competencies/C1/close",
        json={"text": "p", "example": "e", "declaration": ORCHARD},
    )

    assert closed.status_code == 200
    assert readings.asked == ["iris/orchard"]


def test_verify_passes_a_course_folder_reading_nothing_by_default() -> None:
    result = verify(NOTHING_BY_DEFAULT_FIXTURE.folder)

    assert result.returncode == 0, result.stdout + result.stderr


def test_verify_refuses_any_other_value(tmp_path: Path) -> None:
    folder = write_course_folder(
        tmp_path, with_every_competency(), read_when_none_declared="upstream"
    )

    result = verify(folder)

    assert result.returncode != 0
    assert "read_when_none_declared" in result.stdout
    assert "'roster'" in result.stdout and "'nothing'" in result.stdout


def test_the_app_refuses_to_start_on_any_other_value(
    tmp_path: Path, make_client: MakeClient, test_settings: Settings
) -> None:
    folder = write_course_folder(
        tmp_path, with_every_competency(), read_when_none_declared="upstream"
    )

    with pytest.raises(ConfigurationError, match="read_when_none_declared"):
        make_client(settings=on(test_settings, folder))


def test_reading_the_rosters_the_app_refuses_a_row_naming_no_evidence_project(
    tmp_path: Path, make_client: MakeClient, test_settings: Settings
) -> None:
    roster = tmp_path / "roster.csv"
    roster.write_text(
        "github_login,github_id,name,group,evidence_project\n"
        "nobody,1,No Body,Lighthouse,\n",
        encoding="utf-8",
    )
    settings = test_settings.model_copy(
        update={
            "course_folder": str(ONE_GROUP_FIXTURE.folder),
            "roster_file": str(roster),
        }
    )

    with pytest.raises(ConfigurationError, match="line 2: no Evidence Project"):
        make_client(settings=settings)
