import base64
import json
from pathlib import Path

import httpx
import pytest
from courses_under_test import NOTHING_BY_DEFAULT_FIXTURE

from app.repository_reading import (
    GitHubWorkspaceData,
    InMemoryReadings,
    RepositoryReader,
    StudentToRead,
    WorkspaceDataReadings,
)
from app.repository_reading.batch import (
    BatchResult,
    evidence_projects,
    main,
    run_batch,
    summary,
)
from app.repository_reading.recorded import RecordedGitHub
from app.roster import parse_roster
from app.settings import ConfigurationError
from app.store import DeclarationPayload, InMemoryStore

from .conftest import FIXTURES, MATHUTRICE, NOW, OCEENS, REPOSITORIES

ROSTER = (
    "github_login,github_id,name,group,evidence_project\r\n"
    "dorothy-math,1,A,MATHutrice,dorothy-math/MATHutrice\r\n"
    "radia-oceens,2,B,OcéENS,radia-oceens/OceENS\r\n"
    "barbara-oceens,3,C,OcéENS,barbara-oceens/OceENS\r\n"
)
UPSTREAMS = {"OcéENS": OCEENS, "MATHutrice": MATHUTRICE}


class WorkspaceDataInMemory:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.commits: list[str] = []

    def read(self, path: str) -> bytes | None:
        return self.files.get(path)

    def write(self, files: dict[str, bytes], message: str) -> None:
        self.files.update(files)
        self.commits.append(message)


def recorded_github(*names: str) -> RecordedGitHub:
    return RecordedGitHub.load(*(FIXTURES / f"{n}.json.gz" for n in names))


def roster_students(csv_text: str) -> list[StudentToRead]:
    return evidence_projects(
        list(parse_roster(csv_text, UPSTREAMS, names_evidence_projects=True)),
        InMemoryStore(),
        UPSTREAMS,
    ).to_read


def test_the_roster_gives_each_students_evidence_project() -> None:
    students = roster_students(ROSTER)
    assert [s.evidence_project for s in students] == [
        "dorothy-math/MATHutrice",
        "radia-oceens/OceENS",
        "barbara-oceens/OceENS",
    ]
    assert students[1].upstream == "EPF-MDE/OceENS"


def test_a_declared_evidence_project_is_read_instead_and_a_gitlab_one_is_named() -> (
    None
):
    dorothy, radia, barbara = parse_roster(
        ROSTER, UPSTREAMS, names_evidence_projects=True
    )
    store = InMemoryStore()
    store.send_declaration(
        radia,
        DeclarationPayload(
            url="https://github.com/radia/notes",
            what_to_read="n",
            repository_path="radia/notes",
            host="github",
            access_when_declared="readable",
        ),
    )
    store.send_declaration(
        barbara,
        DeclarationPayload(
            url="https://gitlab.com/b/api",
            what_to_read="n",
            repository_path="b/api",
            host="gitlab",
            access_when_declared="gitlab",
        ),
    )

    found = evidence_projects([dorothy, radia, barbara], store, UPSTREAMS)

    assert [(s.login, s.evidence_project) for s in found.to_read] == [
        ("dorothy-math", "dorothy-math/MATHutrice"),
        ("radia-oceens", "radia/notes"),
    ]
    assert found.gitlab == {"barbara-oceens": "b/api"}

    store.withdraw_declaration(radia)
    found = evidence_projects([radia], store, UPSTREAMS)
    assert found.to_read[0].evidence_project == "radia-oceens/OceENS"


def test_without_the_store_only_the_roster_is_read() -> None:
    dorothy, radia = list(
        parse_roster(ROSTER, UPSTREAMS, names_evidence_projects=True)
    )[:2]

    found = evidence_projects([dorothy, radia], None, UPSTREAMS)

    assert [(s.login, s.evidence_project) for s in found.to_read] == [
        ("dorothy-math", "dorothy-math/MATHutrice"),
        ("radia-oceens", "radia-oceens/OceENS"),
    ]


def test_reading_nothing_a_student_who_declared_nothing_is_listed_not_declared() -> (
    None
):
    course = NOTHING_BY_DEFAULT_FIXTURE
    iris, olive = course.roster(course.roster_csv)
    store = InMemoryStore()
    store.send_declaration(
        olive,
        DeclarationPayload(
            url="https://github.com/olive/orchard",
            what_to_read="n",
            repository_path="olive/orchard",
            host="github",
            access_when_declared="readable",
        ),
    )

    found = evidence_projects([iris, olive], store, {"Orchard": None})

    assert found.not_declared == [iris.github_login]
    assert [(s.login, s.evidence_project) for s in found.to_read] == [
        (olive.github_login, "olive/orchard")
    ]
    assert evidence_projects([iris], None, {"Orchard": None}).not_declared == [
        iris.github_login
    ]
    assert (
        f"\n  {iris.github_login}: not declared: no Evidence Project to read"
        in summary(BatchResult(), found)
    )


def test_the_batch_stores_one_file_per_student_in_one_commit() -> None:
    data = WorkspaceDataInMemory()
    reader = RepositoryReader(
        recorded_github("empty-repository", "fallback-default", "deleted-pr-branch"),
        InMemoryReadings(),
        now=lambda: NOW,
    )

    result = run_batch(roster_students(ROSTER), reader, data)

    assert result.failures == {}
    assert sorted(data.files) == [
        "repository-readings/barbara-oceens.json",
        "repository-readings/dorothy-math.json",
        "repository-readings/radia-oceens.json",
    ]
    assert len(data.commits) == 1
    assert (
        json.loads(data.files["repository-readings/dorothy-math.json"])["branches_read"]
        == 1
    )


def test_a_repository_that_cannot_be_read_is_named_and_the_others_are_stored() -> None:
    data = WorkspaceDataInMemory()
    github = recorded_github(
        "empty-repository", "fallback-default", "deleted-pr-branch"
    )
    github.set("repos/radia-oceens/OceENS", 404, {"message": "Not Found"})
    reader = RepositoryReader(github, InMemoryReadings(), now=lambda: NOW)

    result = run_batch(roster_students(ROSTER), reader, data)

    assert list(result.failures) == ["radia-oceens"]
    assert "repository-readings/barbara-oceens.json" in data.files


def test_the_app_reads_the_batch_file_without_asking_github() -> None:
    data = WorkspaceDataInMemory()
    run_batch(
        roster_students(ROSTER),
        RepositoryReader(
            recorded_github(
                "empty-repository", "fallback-default", "deleted-pr-branch"
            ),
            InMemoryReadings(),
            now=lambda: NOW,
        ),
        data,
    )
    github = recorded_github()
    app_reader = RepositoryReader(github, WorkspaceDataReadings(data), now=lambda: NOW)

    reading = app_reader.read(REPOSITORIES["deleted-pr-branch"])

    assert github.requests == []
    assert reading.pull_requests_read == 4


def test_a_repository_missing_from_the_batch_is_read_on_first_view_and_stored() -> None:
    data = WorkspaceDataInMemory()
    github = recorded_github("work-off-default")
    app_reader = RepositoryReader(github, WorkspaceDataReadings(data), now=lambda: NOW)

    reading = app_reader.read(REPOSITORIES["work-off-default"])

    assert github.requests
    assert "repository-readings/rosalind-oceens.json" in data.files
    assert not reading.empty


def test_writing_to_workspace_data_is_one_commit_retried_when_the_branch_moved() -> (
    None
):
    calls: list[str] = []
    heads = iter(["a" * 40, "b" * 40])
    moves = iter([422, 200])

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path.endswith("/git/ref/heads/workspace-data"):
            return httpx.Response(200, json={"object": {"sha": next(heads)}})
        if "/git/commits/" in path:
            return httpx.Response(200, json={"tree": {"sha": "t" * 40}})
        if path.endswith("/git/trees"):
            tree = json.loads(request.content)["tree"]
            assert [t["path"] for t in tree] == [
                "repository-readings/a.json",
                "repository-readings/b.json",
            ]
            return httpx.Response(201, json={"sha": "n" * 40})
        if path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "c" * 40})
        if path.endswith("/git/refs/heads/workspace-data"):
            return httpx.Response(next(moves), json={})
        return httpx.Response(404)

    data = GitHubWorkspaceData(
        "demo-school/demo-course",
        lambda: "token",
        client=httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(handle)
        ),
    )
    data.write(
        {"repository-readings/a.json": b"{}", "repository-readings/b.json": b"{}"},
        "data: batch",
    )

    assert (
        calls.count(
            "PATCH /repos/demo-school/demo-course/git/refs/heads/workspace-data"
        )
        == 2
    )
    assert calls.count("POST /repos/demo-school/demo-course/git/trees") == 2


def test_reading_a_file_from_workspace_data() -> None:
    content = base64.b64encode(b"github_login\r\n").decode()

    def handle(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path.endswith("/contents/roster.csv")
            and request.url.params["ref"] == "workspace-data"
        ):
            return httpx.Response(200, json={"content": content, "sha": "s"})
        return httpx.Response(404)

    data = GitHubWorkspaceData(
        "demo-school/demo-course",
        lambda: "token",
        client=httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(handle)
        ),
    )
    assert data.read("roster.csv") == b"github_login\r\n"
    assert data.read("repository-readings/nobody.json") is None


def test_the_batch_without_a_repository_refuses_before_asking_github(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("WORKSPACE_REPOSITORY", "")
    roster = tmp_path / "roster.csv"
    roster.write_text(ROSTER, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"WORKSPACE_REPOSITORY\b"):
        main(["--roster", str(roster)])
