"""The fork panel: what the Reading Day would find on the Student's fork today,
per Competency, as facts tied to points and never a Band (#468)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import ADA, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.fork_panel import FakeAccessCheck, OfflineForkReading
from app.fork_reading import CompetencyReading, Fact, ForkReading, StudentFork
from app.settings import Settings
from app.store import InMemoryStore

READ_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
ADA_FORK = StudentFork("ada-oceens", "OcéENS", "ada-oceens/OceENS")


def reading(
    student: StudentFork = ADA_FORK,
    empty: bool = False,
    branches: int = 3,
    pulls: int = 2,
) -> ForkReading:
    c1 = (
        []
        if empty
        else [
            Fact(
                "C1",
                "`feature/cache` changes 2 files beyond `course-2026`, 40 lines added; "
                "last change on 2026-10-13.",
                link="https://github.com/ada-oceens/OceENS/compare/a...b",
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
                "C2.c",
                "The ruleset on `main` requires `architecture` and `test`.",
                link="https://x/rules",
            ),
            Fact(
                "C2.b",
                "`main` contains the Clean Bench Fallback Branch.",
                credited_to="course-2026-fallback-clean-bench",
            ),
        ]
    )
    return ForkReading(
        student=student,
        default_branch="main",
        read_at=READ_AT,
        checked_at=READ_AT,
        branches_read=branches,
        pull_requests_read=pulls,
        empty=empty,
        competencies={
            "C1": CompetencyReading("C1", c1, [] if c1 else ["C1"], []),
            "C2": CompetencyReading(
                "C2", c2, ["C2.a", "C2.d", "C2.e"], ["C2.f", "C2.g"]
            ),
            "C3": CompetencyReading(
                "C3", [], ["C3.b", "C3.e"], ["C3.a", "C3.c", "C3.d", "C3.f"]
            ),
        },
    )


@pytest.fixture
def forks() -> OfflineForkReading:
    """The fake fork reading every client of a test shares: readings set by the test."""
    return OfflineForkReading()


@pytest.fixture
def panel_client(make_client: MakeClient, forks: OfflineForkReading) -> TestClient:
    return make_client(
        fork_reading=forks, access_check=FakeAccessCheck(readable={"ada-oceens/bakery"})
    )


def test_each_fact_names_the_point_it_supports(
    panel_client: TestClient, forks: OfflineForkReading
) -> None:
    forks.put(reading())
    sign_in(panel_client, ADA)

    panel = panel_client.get("/api/competencies/C1/fork").json()

    c2 = panel_client.get("/api/competencies/C2/fork").json()
    assert [(f["point"], f["text"]) for f in c2["facts"]][0] == (
        "C2.c",
        "The ruleset on `main` requires `architecture` and `test`.",
    )
    assert c2["facts"][1]["credited_to"] == "course-2026-fallback-clean-bench"
    assert panel["facts"][0]["point"] == "C1"


def test_a_point_the_fork_cannot_show_says_to_show_it_at_the_eval(
    panel_client: TestClient, forks: OfflineForkReading
) -> None:
    forks.put(reading())
    sign_in(panel_client, ADA)

    c2 = panel_client.get("/api/competencies/C2/fork").json()
    c3 = panel_client.get("/api/competencies/C3/fork").json()

    assert c2["not_visible"] == [
        {"point": "C2.f", "text": "Not visible from your fork: show it at the Eval"},
        {"point": "C2.g", "text": "Not visible from your fork: show it at the Eval"},
    ]
    assert {n["point"] for n in c3["not_visible"]} == {"C3.a", "C3.c", "C3.d", "C3.f"}
    assert all("show your PostHog at the Eval" in n["text"] for n in c3["not_visible"])
    assert c2["nothing_found_text"] == (
        "Looked for on your fork (3 branches, 2 pull requests read), "
        "nothing found yet: C2.a, C2.d, C2.e."
    )


def test_c1s_changed_files_come_with_a_sentence_saying_the_workspace_does_not_judge_them(  # noqa: E501
    panel_client: TestClient, forks: OfflineForkReading
) -> None:
    forks.put(reading())
    sign_in(panel_client, ADA)

    c1 = panel_client.get("/api/competencies/C1/fork").json()

    assert "does not judge them" in c1["not_judged"]
    assert c1["facts"][0]["files"] == [{"path": "app/cache.py", "additions": 30}]
    assert (
        c1["facts"][0]["link"] == "https://github.com/ada-oceens/OceENS/compare/a...b"
    )
    assert panel_client.get("/api/competencies/C2/fork").json()["not_judged"] is None


def test_an_empty_fork_says_where_it_looked_what_to_do_and_that_it_is_not_a_zero(
    panel_client: TestClient, forks: OfflineForkReading
) -> None:
    forks.put(reading(empty=True, branches=1, pulls=0))
    sign_in(panel_client, ADA)

    c1 = panel_client.get("/api/competencies/C1/fork").json()

    assert c1["empty"] is True
    text = c1["empty_text"]
    assert text.startswith(
        "On your fork, no branch or pull request changes a file beyond the "
        "course's code (1 branch, 0 pull requests read)."
    )
    assert "What to do next" in text
    assert "a provisional reading, not a zero" in text
    assert c1["facts"] == []


def test_the_panel_shows_when_the_fork_was_read_and_a_refresh_writes_nothing_to_the_record(  # noqa: E501
    panel_client: TestClient, forks: OfflineForkReading, store: InMemoryStore
) -> None:
    forks.put(reading())
    sign_in(panel_client, ADA)
    before = store.writes

    shown = panel_client.get("/api/competencies/C2/fork").json()
    refreshed = panel_client.post("/api/competencies/C2/fork/refresh").json()

    assert shown["read_at"] == shown["checked_at"] == "2026-11-01T08:00:00Z"
    assert refreshed["read_at"] == shown["read_at"]
    assert refreshed["checked_at"] > shown["checked_at"]
    assert forks.refreshes == 1
    assert store.writes == before


def test_a_fork_that_cannot_be_read_now_is_said_plainly_never_a_zero(
    make_client: MakeClient,
) -> None:
    class Down:
        def read(self, student: StudentFork) -> ForkReading:
            raise RuntimeError("The GitHub App has no installation")

        refresh = read

    client = make_client(fork_reading=Down(), access_check=FakeAccessCheck())
    sign_in(client, ADA)

    panel = client.get("/api/competencies/C1/fork")

    assert panel.status_code == 200
    assert panel.json()["available"] is False
    assert "could not be read just now" in panel.json()["unavailable"]
    assert client.post("/api/competencies/C1/fork/refresh").json()["available"] is False


def test_an_unknown_competency_has_no_panel(panel_client: TestClient) -> None:
    sign_in(panel_client, ADA)
    assert panel_client.get("/api/competencies/C9/fork").status_code == 404


def test_the_panel_needs_a_signed_in_student(panel_client: TestClient) -> None:
    assert panel_client.get("/api/competencies/C1/fork").status_code == 401


def test_with_the_real_fork_reading_the_app_starts_even_before_the_student_connector_is_installed(  # noqa: E501
    make_client: MakeClient, test_settings: Settings
) -> None:
    # No installation, no key here: building the reading fails on first view,
    # and the panel says so.
    settings = test_settings.model_copy(update={"fork_reading": "github"})
    client = make_client(settings=settings, access_check=FakeAccessCheck())
    sign_in(client, ADA)

    panel = client.get("/api/competencies/C1/fork").json()

    assert panel["available"] is False
