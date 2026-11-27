from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
)

READ_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
CLEAN_BENCH = Credit("course-2026-fallback-clean-bench")
POSTHOG = Credit("course-2026-fallback-posthog")


def reading_of(student: OnTheRoster, c2: list[Fact]) -> RepositoryReading:
    return RepositoryReading(
        student=student.to_read(),
        default_branch="main",
        facts_computed_at=READ_AT,
        last_checked_at=READ_AT,
        branches_read=2,
        pull_requests_read=1,
        empty=False,
        competencies={
            "C2": CompetencyReading(
                "C2",
                c2,
                [
                    p
                    for p in (PointId.C2_A, PointId.C2_B)
                    if p not in {f.point for f in c2}
                ],
                [],
            ),
        },
    )


def c2_panel(make_client: MakeClient, student: OnTheRoster, c2: list[Fact]) -> Any:
    repositories = OfflineRepositoryReading()
    repositories.put(reading_of(student, c2))
    client: TestClient = make_client(
        repository_reading=repositories, access_check=FakeAccessCheck()
    )
    sign_in(client, student.github_id)
    return client.get("/api/competencies/C2/evidence-panel").json()


def test_a_point_whose_only_facts_come_from_a_fallback_branch_is_received_from_the_course(  # noqa: E501
    make_client: MakeClient, student: OnTheRoster
) -> None:
    panel = c2_panel(
        make_client,
        student,
        [Fact(PointId.C2_B, "`main` contains it.", credited_to=CLEAN_BENCH)],
    )

    assert [r["point"] for r in panel["received"]] == ["C2.b"]
    assert "Clean Bench Fallback Branch" in panel["received"][0]["text"]
    assert panel["nothing_found"] == ["C2.a"]
    assert panel["facts"] == []
    received_fact = panel["received"][0]["facts"][0]
    assert received_fact["received_from"] == "the Clean Bench Fallback Branch"


def test_a_point_the_students_own_work_shows_is_found_not_received(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    panel = c2_panel(
        make_client,
        student,
        [
            Fact(PointId.C2_B, "`main` contains it.", credited_to=CLEAN_BENCH),
            Fact(PointId.C2_B, "The Architecture Check runs from your workflow."),
        ],
    )

    assert panel["received"] == []
    assert [f["point"] for f in panel["facts"]] == ["C2.b", "C2.b"]
    assert panel["nothing_found"] == ["C2.a"]
    assert panel["facts"][1]["received_from"] is None


def test_a_point_received_from_two_branches_names_both(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    panel = c2_panel(
        make_client,
        student,
        [
            Fact(PointId.C2_B, "`main` contains it.", credited_to=CLEAN_BENCH),
            Fact(PointId.C2_B, "`main` is built on it.", credited_to=POSTHOG),
            Fact(PointId.C2_A, "Built on a branch.", credited_to=Credit("v2")),
        ],
    )

    by_point = {r["point"]: r["text"] for r in panel["received"]}
    assert "Clean Bench Fallback Branch and the PostHog Fallback" in by_point["C2.b"]
    assert "the course's branch `v2`" in by_point["C2.a"]
    assert panel["nothing_found"] == []
