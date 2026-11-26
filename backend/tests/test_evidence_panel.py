from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import MakeClient, sign_in
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading
from app.repository_reading import (
    CompetencyReading,
    Credit,
    Fact,
    PointId,
    RepositoryReading,
    StudentToRead,
)
from app.settings import Settings
from app.store import InMemoryStore

FRESH_READING_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def reading(
    student: OnTheRoster,
    empty: bool = False,
    branches: int = 3,
    pulls: int = 2,
) -> RepositoryReading:
    c1 = (
        []
        if empty
        else [
            Fact(
                PointId.CHANGED_FILES,
                "`feature/cache` changes 2 files beyond `course-2026`, 40 lines added; "
                "last change on 2026-10-13.",
                link=f"https://github.com/{student.evidence_project}/compare/a...b",
                detail={
                    "branch": "feature/cache",
                    "files": [{"path": "app/cache.py", "additions": 30}],
                },
            )
        ]
    )
    c2 = (
        []
        if empty
        else [
            Fact(
                PointId.C2_C,
                "The ruleset on `main` requires `architecture` and `test`.",
                link="https://x/rules",
            ),
            Fact(
                PointId.C2_B,
                "`main` contains the Clean Bench Fallback Branch.",
                credited_to=Credit("course-2026-fallback-clean-bench"),
            ),
        ]
    )
    return RepositoryReading(
        student=student.to_read(),
        default_branch="main",
        facts_computed_at=FRESH_READING_AT,
        last_checked_at=FRESH_READING_AT,
        branches_read=branches,
        pull_requests_read=pulls,
        empty=empty,
        competencies={
            "C1": CompetencyReading(
                "C1", c1, [] if c1 else [PointId.CHANGED_FILES], []
            ),
            "C2": CompetencyReading(
                "C2",
                c2,
                [PointId.C2_A, PointId.C2_D, PointId.C2_E],
                [PointId.C2_F, PointId.C2_G],
            ),
            "C3": CompetencyReading(
                "C3",
                [],
                [PointId.C3_B, PointId.C3_E],
                [PointId.C3_A, PointId.C3_C, PointId.C3_D, PointId.C3_F],
            ),
        },
    )


@pytest.fixture
def repositories() -> OfflineRepositoryReading:
    return OfflineRepositoryReading()


@pytest.fixture
def panel_client(
    make_client: MakeClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> TestClient:
    client = make_client(
        repository_reading=repositories, access_check=FakeAccessCheck()
    )
    sign_in(client, student.github_id)
    return client


def test_each_fact_names_the_point_it_supports(
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))

    panel = panel_client.get("/api/competencies/C1/evidence-panel").json()

    c2 = panel_client.get("/api/competencies/C2/evidence-panel").json()
    assert [(f["point"], f["text"]) for f in c2["facts"]][0] == (
        "C2.c",
        "The ruleset on `main` requires `architecture` and `test`.",
    )
    assert c2["facts"][1]["credited_to"] == "course-2026-fallback-clean-bench"
    assert panel["facts"][0]["point"] == "C1"


def test_a_point_the_repository_cannot_show_gives_its_statement_and_says_to_show_it_at_the_eval(  # noqa: E501
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))

    c2 = panel_client.get("/api/competencies/C2/evidence-panel").json()
    c3 = panel_client.get("/api/competencies/C3/evidence-panel").json()

    assert c2["not_visible"] == [
        {
            "point": "C2.f",
            "statement": "DEPLOY-STATEMENT: a deployment rolled back.",
            "text": "Not visible from your Evidence Project: show it at the Eval",
        },
        {
            "point": "C2.g",
            "statement": None,
            "text": "Not visible from your Evidence Project: show it at the Eval",
        },
    ]
    assert {n["point"] for n in c3["not_visible"]} == {"C3.a", "C3.c", "C3.d", "C3.f"}
    assert all("show your PostHog at the Eval" in n["text"] for n in c3["not_visible"])


def test_a_point_not_found_yet_gives_its_statement_and_its_to_get_there(  # noqa: E501
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))

    c2 = panel_client.get("/api/competencies/C2/evidence-panel").json()

    assert c2["nothing_found_text"] == (
        "Looked for on your Evidence Project (3 branches, 2 pull requests read), "
        "nothing found yet:"
    )
    assert c2["nothing_found"] == [
        {
            "point": "C2.a",
            "statement": "JOB-STATEMENT: which job stops which mistake.",
            "to_get_there": "JOB-REDO: turn your own pipeline red.",
        },
        {"point": "C2.d", "statement": None, "to_get_there": None},
        {"point": "C2.e", "statement": None, "to_get_there": None},
    ]


def test_a_point_without_a_to_get_there_just_below_the_top_takes_the_highest_it_has(
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    found = reading(student)
    c2 = found.competencies["C2"]
    found.competencies["C2"] = CompetencyReading(
        "C2", [], [PointId.C2_B], c2.not_visible
    )
    repositories.put(found)

    c2_panel = panel_client.get("/api/competencies/C2/evidence-panel").json()

    assert c2_panel["nothing_found"] == [
        {
            "point": "C2.b",
            "statement": "REQUIRED-STATEMENT: a job required before a merge.",
            "to_get_there": "REQUIRED-UNDERSTAND: find which jobs are required.",
        }
    ]


def test_a_fact_gives_the_statement_of_the_point_it_supports(
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))

    c2 = panel_client.get("/api/competencies/C2/evidence-panel").json()

    assert [(f["point"], f["statement"]) for f in c2["facts"]] == [
        ("C2.c", None),
        ("C2.b", "REQUIRED-STATEMENT: a job required before a merge."),
    ]


def test_c1s_changed_files_come_with_a_sentence_saying_the_workspace_does_not_judge_them(  # noqa: E501
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))

    c1 = panel_client.get("/api/competencies/C1/evidence-panel").json()

    assert "does not judge them" in c1["not_judged"]
    assert c1["facts"][0]["files"] == [
        {"path": "app/cache.py", "additions": 30, "changes": None}
    ]
    assert c1["facts"][0]["link"] == (
        f"https://github.com/{student.evidence_project}/compare/a...b"
    )
    assert (
        panel_client.get("/api/competencies/C2/evidence-panel").json()["not_judged"]
        is None
    )


def test_an_empty_repository_says_where_it_looked_what_to_do_and_that_it_is_not_a_zero(
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student, empty=True, branches=1, pulls=0))

    c1 = panel_client.get("/api/competencies/C1/evidence-panel").json()

    assert c1["empty"] is True
    text = c1["empty_text"]
    assert text.startswith(
        "On your Evidence Project, no branch or pull request changes a file "
        "beyond the course's code (1 branch, 0 pull requests read)."
    )
    assert "What to do next" in text
    assert "a provisional reading, not a zero" in text
    assert c1["facts"] == []


def test_the_panel_shows_when_the_repository_was_read_and_a_refresh_writes_nothing_to_the_record(  # noqa: E501
    panel_client: TestClient,
    repositories: OfflineRepositoryReading,
    store: InMemoryStore,
    student: OnTheRoster,
) -> None:
    repositories.put(reading(student))
    before = store.writes

    shown = panel_client.get("/api/competencies/C2/evidence-panel").json()
    refreshed = panel_client.post("/api/competencies/C2/evidence-panel/refresh").json()

    assert (
        shown["facts_computed_at"] == shown["last_checked_at"] == "2026-11-01T08:00:00Z"
    )
    assert refreshed["facts_computed_at"] == shown["facts_computed_at"]
    assert refreshed["last_checked_at"] > shown["last_checked_at"]
    assert repositories.refreshes == 1
    assert store.writes == before


def test_a_repository_that_cannot_be_read_now_is_said_plainly_never_a_zero(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    class Down:
        def read(self, student: StudentToRead) -> RepositoryReading:
            raise RuntimeError("The GitHub App has no installation")

        refresh = read

    client = make_client(repository_reading=Down(), access_check=FakeAccessCheck())
    sign_in(client, student.github_id)

    panel = client.get("/api/competencies/C1/evidence-panel")

    assert panel.status_code == 200
    assert panel.json()["unavailable"] is not None
    assert "could not be read just now" in panel.json()["unavailable"]
    assert (
        client.post("/api/competencies/C1/evidence-panel/refresh").json()["unavailable"]
        is not None
    )


def test_an_unknown_competency_has_no_panel(panel_client: TestClient) -> None:
    assert panel_client.get("/api/competencies/C9/evidence-panel").status_code == 404


def test_the_panel_needs_a_signed_in_student(client: TestClient) -> None:
    assert client.get("/api/competencies/C1/evidence-panel").status_code == 401


def test_with_the_real_repository_reading_the_app_starts_even_before_the_student_connector_is_installed(  # noqa: E501
    make_client: MakeClient, test_settings: Settings, student: OnTheRoster
) -> None:
    settings = test_settings.model_copy(
        update={
            "repository_reading": "github",
            "repository": "demo-school/demo-course",
        }
    )
    client = make_client(settings=settings, access_check=FakeAccessCheck())
    sign_in(client, student.github_id)

    panel = client.get("/api/competencies/C1/evidence-panel").json()

    assert panel["unavailable"] is not None
