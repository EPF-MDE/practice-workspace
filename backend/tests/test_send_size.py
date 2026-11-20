"""Every send fits one GitHub comment (65,536 characters): through the API, a text
too long is refused with a clear 422 the Student can act on, never a 503 that
says "try again" forever. Measured on the GitHub Store, GitHub's HTTP faked."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import ADA, MakeClient, sign_in
from fake_github import FakeGitHub
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading
from app.repository_reading import (
    CompetencyReading,
    Fact,
    RepositoryReading,
    StudentToRead,
)
from app.store import GitHubStore

C1 = "/api/competencies/C1"
READ_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def a_repository_with_very_many_files() -> RepositoryReading:
    files = [
        {"path": f"src/module_{i:05}/a_long_file_name.py", "additions": i}
        for i in range(3000)
    ]
    fact = Fact(
        "C1",
        "`feature/cache` changes 3000 files beyond `course-2026`; "
        "last change on 2026-10-13.",
        link="https://github.com/ada-oceens/OceENS/compare/a...b",
        detail={"branch": "feature/cache", "files": files},
    )
    return RepositoryReading(
        student=StudentToRead("ada-oceens", "OcéENS", "ada-oceens/OceENS"),
        default_branch="main",
        read_at=READ_AT,
        checked_at=READ_AT,
        branches_read=3,
        pull_requests_read=2,
        empty=False,
        competencies={
            "C1": CompetencyReading("C1", [fact], [], []),
            "C2": CompetencyReading("C2", [], ["C2.a"], ["C2.f", "C2.g"]),
            "C3": CompetencyReading("C3", [], ["C3.b"], ["C3.a"]),
        },
    )


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()  # refuses a comment over 65,536 characters, as GitHub does


@pytest.fixture
def ada(make_client: MakeClient, github: FakeGitHub) -> TestClient:
    repositories = OfflineRepositoryReading()
    repositories.put(a_repository_with_very_many_files())
    client = make_client(
        store=GitHubStore(github.client(), github.repository),
        repository_reading=repositories,
        access_check=FakeAccessCheck(),
    )
    sign_in(client, ADA)
    client.post(
        f"{C1}/self-assessment",
        json={"levels": {"C1.a": {"level": "understand", "link": None}}},
    )
    return client


def test_the_longest_closing_send_with_a_repository_of_very_many_files_fits_one_comment(
    ada: TestClient, github: FakeGitHub
) -> None:
    before = github.writes
    declaration = {"url": "https://github.com/ada/" + "b" * 400, "note": "n" * 2_000}

    closed = ada.post(
        f"{C1}/close",
        json={"text": "p" * 12_000, "example": "e" * 2_000, "declaration": declaration},
    )

    assert closed.status_code == 200
    assert github.writes == before + 1
    assert ada.get(C1).json()["evidence_plan"]["text"] == "p" * 12_000


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
            f"{C1}/declaration",
            {"url": "https://github.com/ada/bakery", "note": "x" * 2_001},
            "note",
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
    ada: TestClient, github: FakeGitHub, path: str, body: dict[str, Any], what: str
) -> None:
    before = github.writes

    refused = ada.post(path, json=body)

    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert isinstance(detail, str)  # a sentence the page shows as it is
    assert what in detail and "too long" in detail
    assert github.writes == before


def test_a_send_within_each_limit_but_too_large_once_stored_gets_a_422_not_a_503(
    ada: TestClient, github: FakeGitHub
) -> None:
    before = github.writes
    # A control character takes six characters once stored (`\u0001`): within
    # the limit, over one comment.
    body = {"text": "\x01" * 12_000, "example": "My README."}

    refused = ada.post(f"{C1}/close", json=body)

    assert refused.status_code == 422
    assert "too long to store" in refused.json()["detail"]
    assert "Retry-After" not in refused.headers
    assert github.writes == before
