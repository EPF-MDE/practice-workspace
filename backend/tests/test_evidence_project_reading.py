"""What the Evidence panel reads, through the HTTP API: the Evidence Project the
Reading Day reads, for every Competency. The one declared, if the App can read it,
else the roster's; a GitLab project or a repository the App cannot read is said as
such, never read as a zero (#514)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import ADA, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading
from app.repository_reading import (
    CompetencyReading,
    Fact,
    InMemoryReadings,
    RepositoryReader,
    RepositoryReading,
    Response,
    StudentToRead,
)

DECLARATION = "/api/evidence-project/declaration"
COMPETENCIES = ("C1", "C2", "C3")
READ_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def panel(client: TestClient, competency: str) -> dict[str, Any]:
    body: dict[str, Any] = client.get(
        f"/api/competencies/{competency}/evidence-panel"
    ).json()
    return body


def declare(client: TestClient, url: str) -> None:
    assert client.post(DECLARATION, json={"url": url, "note": "README"}).is_success


def reading_of(repository: str, ruleset: str) -> RepositoryReading:
    """A reading of `repository` whose one C2 fact names `ruleset`."""
    return RepositoryReading(
        student=StudentToRead("ada-oceens", "OcéENS", repository),
        default_branch="main",
        read_at=READ_AT,
        checked_at=READ_AT,
        branches_read=1,
        pull_requests_read=0,
        empty=False,
        competencies={
            "C1": CompetencyReading("C1", [], ["C1"], []),
            "C2": CompetencyReading(
                "C2", [Fact("C2.c", f"The ruleset `{ruleset}`.")], [], []
            ),
            "C3": CompetencyReading("C3", [], ["C3.b", "C3.e"], []),
        },
    )


class CountedReading(OfflineRepositoryReading):
    """The fake Repository reading, counting the repositories it was asked to read."""

    def __init__(self) -> None:
        super().__init__()
        self.asked: list[str] = []

    def read(self, student: StudentToRead) -> RepositoryReading:
        self.asked.append(student.evidence_project)
        return super().read(student)


@pytest.fixture
def repositories() -> CountedReading:
    source = CountedReading()
    source.put(reading_of("ada-oceens/OceENS", "on the roster's"))
    source.put(reading_of("ada/bakery", "on the bakery"))
    return source


@pytest.fixture
def ada(make_client: MakeClient, repositories: CountedReading) -> TestClient:
    client = make_client(
        repository_reading=repositories,
        access_check=FakeAccessCheck(readable={"ada/bakery"}),
    )
    sign_in(client, ADA)
    return client


def test_a_declared_github_repository_is_read_for_every_competency(
    ada: TestClient,
) -> None:
    declare(ada, "https://github.com/ada/bakery")

    for competency in COMPETENCIES:
        shown = panel(ada, competency)
        assert shown["available"] is True
        assert shown["evidence_project"] == "ada/bakery"
    assert panel(ada, "C2")["facts"][0]["text"] == "The ruleset `on the bakery`."


def test_withdrawing_the_declaration_reads_the_rosters_evidence_project_again(
    ada: TestClient,
) -> None:
    declare(ada, "https://github.com/ada/bakery")
    assert panel(ada, "C2")["facts"][0]["text"] == "The ruleset `on the bakery`."

    ada.delete(DECLARATION)

    shown = panel(ada, "C2")
    assert shown["evidence_project"] == "ada-oceens/OceENS"
    assert shown["facts"][0]["text"] == "The ruleset `on the roster's`."


@pytest.mark.parametrize(
    "url",
    ["https://gitlab.com/ada/bakery", "https://github.com/ada/private-bakery"],
    ids=["a GitLab project", "a repository the App cannot read"],
)
def test_a_project_the_app_cannot_read_is_said_as_such_never_a_zero(
    ada: TestClient, repositories: CountedReading, url: str
) -> None:
    declare(ada, url)
    repositories.asked.clear()

    for competency in COMPETENCIES:
        shown = panel(ada, competency)
        assert shown["available"] is False
        assert shown["unavailable"]
        assert shown["empty"] is False
        assert shown["facts"] == []
        assert shown["evidence_project"] in url
    assert repositories.asked == []  # neither it nor the roster's is read instead


# --- The Repository reading itself, on repositories that are not forks ---------

UPSTREAM_BRANCHES = "repos/EPF-MDE/OceENS/branches?per_page=100"


class OwnRepositories:
    """GitHub, for repositories that share no history with the Group's upstream: each
    has one branch, `main`, holding `files`. Anything else answers 404."""

    def __init__(self, files: dict[str, list[str]]) -> None:
        self.answers: dict[str, Any] = {
            UPSTREAM_BRANCHES: [{"name": "course-2026", "commit": {"sha": "up"}}]
        }
        for repository, paths in files.items():
            sha = f"{repository}-tip"
            self.answers |= {
                f"repos/{repository}": {"default_branch": "main"},
                f"repos/{repository}/branches?per_page=100": [
                    {"name": "main", "commit": {"sha": sha}}
                ],
                f"repos/{repository}/pulls?state=all&per_page=100": [],
                f"repos/{repository}/git/trees/{sha}?recursive=1": {
                    "tree": [{"path": p, "type": "blob"} for p in paths]
                },
                f"repos/{repository}/git/commits/{sha}": {
                    "committer": {"date": "2026-10-13T10:00:00Z"}
                },
            }

    def get(self, path: str) -> Response:
        if path in self.answers:
            return Response(200, self.answers[path])
        return Response(404, {"message": "Not Found"})


def test_a_repository_that_is_not_a_fork_is_read_and_a_change_reads_the_new_one(
    make_client: MakeClient,
) -> None:
    github = OwnRepositories(
        {
            "ada/bakery": ["README.md", "src/oven.py", "package-lock.json"],
            "ada/mill": ["README.md"],
        }
    )
    client = make_client(
        repository_reading=RepositoryReader(github, InMemoryReadings()),
        access_check=FakeAccessCheck(),
    )
    sign_in(client, ADA)

    declare(client, "https://github.com/ada/bakery")
    bakery = panel(client, "C1")

    assert bakery["available"] is True
    assert bakery["empty"] is False
    assert [f["path"] for f in bakery["facts"][0]["files"]] == [
        "README.md",
        "src/oven.py",
    ]

    declare(client, "https://github.com/ada/mill")
    mill = panel(client, "C1")

    assert mill["evidence_project"] == "ada/mill"
    assert [f["path"] for f in mill["facts"][0]["files"]] == ["README.md"]
