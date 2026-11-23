from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import MakeClient, sign_in, store_on
from courses_under_test import OnTheRoster
from fake_github import FakeGitHub
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading
from app.repository_reading import (
    CompetencyReading,
    Fact,
    PointId,
    RepositoryReading,
)

C1 = "/api/competencies/C1"
FRESH_READING_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def a_repository_with_very_many_files(student: OnTheRoster) -> RepositoryReading:
    files = [
        {"path": f"src/module_{i:05}/a_long_file_name.py", "additions": i}
        for i in range(3000)
    ]
    fact = Fact(
        PointId.CHANGED_FILES,
        "`feature/cache` changes 3000 files beyond `course-2026`; "
        "last change on 2026-10-13.",
        link=f"https://github.com/{student.evidence_project}/compare/a...b",
        detail={"branch": "feature/cache", "files": files},
    )
    return RepositoryReading(
        student=student.to_read(),
        default_branch="main",
        facts_computed_at=FRESH_READING_AT,
        last_checked_at=FRESH_READING_AT,
        branches_read=3,
        pull_requests_read=2,
        empty=False,
        competencies={
            "C1": CompetencyReading("C1", [fact], [], []),
            "C2": CompetencyReading(
                "C2", [], [PointId.C2_A], [PointId.C2_F, PointId.C2_G]
            ),
            "C3": CompetencyReading("C3", [], [PointId.C3_B], [PointId.C3_A]),
        },
    )


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def signed_in(
    make_client: MakeClient, github: FakeGitHub, student: OnTheRoster
) -> TestClient:
    repositories = OfflineRepositoryReading()
    repositories.put(a_repository_with_very_many_files(student))
    client = make_client(
        store=store_on(github),
        repository_reading=repositories,
        access_check=FakeAccessCheck(),
    )
    sign_in(client, student.github_id)
    client.post(
        f"{C1}/self-assessment",
        json={"levels": {"C1.a": {"level": "understand", "link": None}}},
    )
    return client


def test_the_longest_closing_send_with_a_repository_of_very_many_files_fits_one_comment(
    signed_in: TestClient, github: FakeGitHub
) -> None:
    before = github.write_requests
    declaration = {
        "url": "https://github.com/ada/" + "b" * 400,
        "what_to_read": "n" * 2_000,
    }

    closed = signed_in.post(
        f"{C1}/close",
        json={"text": "p" * 12_000, "example": "e" * 2_000, "declaration": declaration},
    )

    assert closed.status_code == 200
    assert github.write_requests == before + 1
    assert signed_in.get(C1).json()["evidence_plan"]["text"] == "p" * 12_000


@pytest.mark.parametrize(
    "path, body, what",
    [
        (
            f"{C1}/steps/guided-calculation/answer",
            {"fields": {"sentence": "x" * 4_001}},
            "sentence",
        ),
        (f"{C1}/evidence-plan", {"text": "x" * 12_001}, "Evidence Plan"),
        (f"{C1}/close", {"text": "x" * 12_001, "example": "e"}, "Evidence Plan"),
        (f"{C1}/close", {"text": "p", "example": "x" * 2_001}, "example"),
        (
            "/api/evidence-project/declaration",
            {"url": "https://github.com/ada/bakery", "what_to_read": "x" * 2_001},
            "note",
        ),
        (
            "/api/evidence-project/declaration",
            {"url": "https://github.com/ada/" + "b" * 500, "what_to_read": "n"},
            "URL",
        ),
        (
            f"{C1}/close",
            {
                "text": "p",
                "example": "e",
                "declaration": {
                    "url": "https://github.com/ada/bakery",
                    "what_to_read": "x" * 2_001,
                },
            },
            "note",
        ),
        (
            "/api/evidence-project/check",
            {"url": "https://github.com/ada/" + "b" * 500},
            "URL",
        ),
        (
            f"{C1}/steps/guided-calculation/questions",
            {"text": "x" * 4_001},
            "question",
        ),
        (
            f"{C1}/self-assessment",
            {
                "levels": {
                    "C1.a": {
                        "level": "done",
                        "link": "https://github.com/a/b/" + "x" * 500,
                    }
                }
            },
            "link",
        ),
    ],
)
def test_a_text_over_its_limit_gets_a_clear_422_and_nothing_is_stored(
    signed_in: TestClient,
    github: FakeGitHub,
    path: str,
    body: dict[str, Any],
    what: str,
) -> None:
    before = github.write_requests

    refused = signed_in.post(path, json=body)

    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert isinstance(detail, str)
    assert what in detail and "too long" in detail
    assert github.write_requests == before


def test_a_send_within_each_limit_but_too_large_once_stored_gets_a_422_not_a_503(
    signed_in: TestClient, github: FakeGitHub
) -> None:
    before = github.write_requests
    body = {"text": "\x01" * 12_000, "example": "My README."}

    refused = signed_in.post(f"{C1}/close", json=body)

    assert refused.status_code == 422
    assert "too long to store" in refused.json()["detail"]
    assert "Retry-After" not in refused.headers
    assert github.write_requests == before


def test_a_send_missing_a_field_and_no_text_too_long_gets_the_usual_422(
    signed_in: TestClient, github: FakeGitHub
) -> None:
    before = github.write_requests

    refused = signed_in.post(f"{C1}/close", json={"text": "My plan."})

    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert isinstance(detail, list)
    assert [error["loc"] for error in detail] == [["body", "example"]]
    assert github.write_requests == before
