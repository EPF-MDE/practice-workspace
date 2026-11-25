from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import MakeClient, sign_in
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading
from app.repository_reading import (
    CompetencyReading,
    Fact,
    InMemoryReadings,
    PointId,
    RepositoryReader,
    RepositoryReading,
    Response,
    StudentToRead,
)

DECLARATION = "/api/evidence-project/declaration"
COMPETENCIES = ("C1", "C2", "C3")
FRESH_READING_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def panel(client: TestClient, competency: str) -> dict[str, Any]:
    body: dict[str, Any] = client.get(
        f"/api/competencies/{competency}/evidence-panel"
    ).json()
    return body


def declare(client: TestClient, url: str) -> None:
    assert client.post(
        DECLARATION, json={"url": url, "what_to_read": "README"}
    ).is_success


def reading_of(
    student: OnTheRoster, repository: str, ruleset: str
) -> RepositoryReading:
    return RepositoryReading(
        student=student.to_read(repository),
        default_branch="main",
        facts_computed_at=FRESH_READING_AT,
        last_checked_at=FRESH_READING_AT,
        branches_read=1,
        pull_requests_read=0,
        empty=False,
        competencies={
            "C1": CompetencyReading("C1", [], [PointId.CHANGED_FILES], []),
            "C2": CompetencyReading(
                "C2", [Fact(PointId.C2_C, f"The ruleset `{ruleset}`.")], [], []
            ),
            "C3": CompetencyReading("C3", [], [PointId.C3_B, PointId.C3_E], []),
        },
    )


class CountedReading(OfflineRepositoryReading):
    def __init__(self) -> None:
        super().__init__()
        self.asked: list[str] = []

    def read(self, student: StudentToRead) -> RepositoryReading:
        self.asked.append(student.evidence_project)
        return super().read(student)


@pytest.fixture
def repositories(student: OnTheRoster) -> CountedReading:
    source = CountedReading()
    source.put(
        reading_of(student, student.to_read().evidence_project, "on the roster's")
    )
    source.put(reading_of(student, "ada/bakery", "on the bakery"))
    return source


@pytest.fixture
def signed_in(
    make_client: MakeClient, repositories: CountedReading, student: OnTheRoster
) -> TestClient:
    client = make_client(
        repository_reading=repositories,
        access_check=FakeAccessCheck(readable={"ada/bakery"}),
    )
    sign_in(client, student.github_id)
    return client


def test_a_declared_github_repository_is_read_for_every_competency(
    signed_in: TestClient,
) -> None:
    declare(signed_in, "https://github.com/ada/bakery")

    for competency in COMPETENCIES:
        shown = panel(signed_in, competency)
        assert shown["unavailable"] is None
        assert shown["evidence_project"] == "ada/bakery"
    assert panel(signed_in, "C2")["facts"][0]["text"] == "The ruleset `on the bakery`."


def test_withdrawing_the_declaration_reads_the_rosters_evidence_project_again(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    declare(signed_in, "https://github.com/ada/bakery")
    assert panel(signed_in, "C2")["facts"][0]["text"] == "The ruleset `on the bakery`."

    signed_in.delete(DECLARATION)

    shown = panel(signed_in, "C2")
    assert shown["evidence_project"] == student.evidence_project
    assert shown["facts"][0]["text"] == "The ruleset `on the roster's`."


@pytest.mark.parametrize(
    "url",
    ["https://gitlab.com/ada/bakery", "https://github.com/ada/private-bakery"],
    ids=["a GitLab project", "a repository the App cannot read"],
)
def test_a_project_the_app_cannot_read_is_said_as_such_never_a_zero(
    signed_in: TestClient, repositories: CountedReading, url: str
) -> None:
    declare(signed_in, url)
    repositories.asked.clear()

    for competency in COMPETENCIES:
        shown = panel(signed_in, competency)
        assert shown["unavailable"]
        assert shown["empty"] is False
        assert shown["facts"] == []
        assert shown["evidence_project"] in url
    assert repositories.asked == []


class UnforkedRepositories:
    def __init__(
        self,
        upstream: str | None,
        files: dict[str, list[str]],
        *,
        linked_to_upstream: tuple[str, ...] = (),
    ) -> None:
        self.answers: dict[str, Any] = {
            f"repos/{upstream}/branches?per_page=100": [
                {"name": "course-2026", "commit": {"sha": "up"}}
            ]
        }
        for repository, paths in files.items():
            sha = f"{repository}-tip"
            self.answers |= {
                f"repos/{repository}": {
                    "default_branch": "main",
                    "source": {"full_name": upstream}
                    if repository in linked_to_upstream
                    else None,
                },
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


def test_a_repository_of_its_own_history_is_read_and_a_change_reads_the_new_one(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    github = UnforkedRepositories(
        student.upstream,
        {
            "ada/bakery": ["README.md", "src/oven.py", "package-lock.json"],
            "ada/mill": ["README.md"],
        },
    )
    client = make_client(
        repository_reading=RepositoryReader(github, InMemoryReadings()),
        access_check=FakeAccessCheck(),
    )
    sign_in(client, student.github_id)

    declare(client, "https://github.com/ada/bakery")
    bakery = panel(client, "C1")

    assert bakery["unavailable"] is None
    assert bakery["empty"] is False
    assert [f["path"] for f in bakery["facts"][0]["files"]] == [
        "README.md",
        "src/oven.py",
    ]

    declare(client, "https://github.com/ada/mill")
    mill = panel(client, "C1")

    assert mill["evidence_project"] == "ada/mill"
    assert [f["path"] for f in mill["facts"][0]["files"]] == ["README.md"]


def test_a_repository_linked_to_the_upstream_it_cannot_be_compared_with_shows_no_files(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    github = UnforkedRepositories(
        student.upstream,
        {"ada/linked-fork": ["README.md", "src/app.py"]},
        linked_to_upstream=("ada/linked-fork",),
    )
    client = make_client(
        repository_reading=RepositoryReader(github, InMemoryReadings()),
        access_check=FakeAccessCheck(),
    )
    sign_in(client, student.github_id)

    declare(client, "https://github.com/ada/linked-fork")

    assert panel(client, "C1")["facts"] == []


ARCHITECTURE_JOB = "jobs:\n  architecture:\n    runs-on: ubuntu-latest\n"
TEST_JOB = "jobs:\n  test:\n    runs-on: ubuntu-latest\n"


@pytest.mark.parametrize(
    ("top_level", "nested", "shown"),
    [(ARCHITECTURE_JOB, TEST_JOB, True), (TEST_JOB, ARCHITECTURE_JOB, False)],
    ids=["a workflow GitHub runs", "a file in a folder GitHub never runs"],
)
def test_the_architecture_check_is_found_only_in_a_workflow_github_runs(
    make_client: MakeClient,
    student: OnTheRoster,
    top_level: str,
    nested: str,
    shown: bool,
) -> None:
    ci, kept = ".github/workflows/ci.yml", ".github/workflows/old/architecture.yml"
    github = UnforkedRepositories(
        student.upstream, {"ada/bakery": ["README.md", ci, kept]}
    )
    contents, tip = "repos/ada/bakery/contents", "ref=ada/bakery-tip"
    github.answers |= {
        f"{contents}/.github/workflows?{tip}": [
            {"type": "file", "name": "ci.yml", "path": ci},
            {"type": "dir", "name": "old", "path": ".github/workflows/old"},
        ],
        f"{contents}/{ci}?{tip}": {"content": b64encode(top_level.encode()).decode()},
        f"{contents}/{kept}?{tip}": {"content": b64encode(nested.encode()).decode()},
    }
    client = make_client(
        repository_reading=RepositoryReader(github, InMemoryReadings()),
        access_check=FakeAccessCheck(),
    )
    sign_in(client, student.github_id)

    declare(client, "https://github.com/ada/bakery")

    found = [
        f["text"]
        for f in panel(client, "C2")["facts"]
        if f["text"].startswith("The Architecture Check runs from")
    ]
    assert found == ([f"The Architecture Check runs from `{ci}` on `main`."] * shown)
