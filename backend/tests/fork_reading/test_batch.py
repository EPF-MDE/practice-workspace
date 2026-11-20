"""The batch reading: every fork on the roster, one file per Student on
`workspace-data`."""

import base64
import json

import httpx

from app.fork_reading import (
    ForkReader,
    GitHubWorkspaceData,
    InMemoryReadings,
    WorkspaceDataReadings,
)
from app.fork_reading.batch import roster_students, run_batch
from app.fork_reading.recorded import RecordedGitHub

from .conftest import FIXTURES, FORKS, NOW

ROSTER = (
    "github_login,github_id,name,group,project,fork\r\n"
    "dorothy-math,1,A,MATHutrice,MATHutrice,dorothy-math/MATHutrice\r\n"
    "radia-oceens,2,B,OcéENS,OcéENS,radia-oceens/OceENS\r\n"
    "barbara-oceens,3,C,OcéENS,OcéENS,barbara-oceens/OceENS\r\n"
)


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


def test_the_roster_gives_each_students_fork() -> None:
    students = roster_students(ROSTER)
    assert [s.fork for s in students] == [
        "dorothy-math/MATHutrice",
        "radia-oceens/OceENS",
        "barbara-oceens/OceENS",
    ]
    assert students[1].upstream == "EPF-MDE/OceENS"


def test_the_batch_stores_one_file_per_student_in_one_commit() -> None:
    data = WorkspaceDataInMemory()
    reader = ForkReader(
        recorded_github("empty-fork", "fallback-default", "deleted-pr-branch"),
        InMemoryReadings(),
        now=lambda: NOW,
    )

    result = run_batch(roster_students(ROSTER), reader, data)

    assert result.failures == {}
    assert sorted(data.files) == [
        "fork-readings/barbara-oceens.json",
        "fork-readings/dorothy-math.json",
        "fork-readings/radia-oceens.json",
    ]
    assert len(data.commits) == 1
    assert (
        json.loads(data.files["fork-readings/dorothy-math.json"])["branches_read"] == 1
    )


def test_a_fork_that_cannot_be_read_is_named_and_the_others_are_stored() -> None:
    data = WorkspaceDataInMemory()
    github = recorded_github("empty-fork", "fallback-default", "deleted-pr-branch")
    github.set("repos/radia-oceens/OceENS", 404, {"message": "Not Found"})
    reader = ForkReader(github, InMemoryReadings(), now=lambda: NOW)

    result = run_batch(roster_students(ROSTER), reader, data)

    assert list(result.failures) == ["radia-oceens"]
    assert "fork-readings/barbara-oceens.json" in data.files


def test_the_app_reads_the_batch_file_without_asking_github() -> None:
    data = WorkspaceDataInMemory()
    run_batch(
        roster_students(ROSTER),
        ForkReader(
            recorded_github("empty-fork", "fallback-default", "deleted-pr-branch"),
            InMemoryReadings(),
            now=lambda: NOW,
        ),
        data,
    )
    github = recorded_github()
    app_reader = ForkReader(github, WorkspaceDataReadings(data), now=lambda: NOW)

    reading = app_reader.read(FORKS["deleted-pr-branch"])

    assert github.requests == []
    assert reading.pull_requests_read == 4


def test_a_fork_missing_from_the_batch_is_read_on_first_view_and_stored() -> None:
    data = WorkspaceDataInMemory()
    github = recorded_github("work-off-default")
    app_reader = ForkReader(github, WorkspaceDataReadings(data), now=lambda: NOW)

    reading = app_reader.read(FORKS["work-off-default"])

    assert github.requests
    assert "fork-readings/rosalind-oceens.json" in data.files
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
                "fork-readings/a.json",
                "fork-readings/b.json",
            ]
            return httpx.Response(201, json={"sha": "n" * 40})
        if path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "c" * 40})
        if path.endswith("/git/refs/heads/workspace-data"):
            return httpx.Response(next(moves), json={})
        return httpx.Response(404)

    data = GitHubWorkspaceData(
        "EPF-MDE/complex-web-services",
        lambda: "token",
        client=httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(handle)
        ),
    )
    data.write(
        {"fork-readings/a.json": b"{}", "fork-readings/b.json": b"{}"}, "data: batch"
    )

    assert (
        calls.count(
            "PATCH /repos/EPF-MDE/complex-web-services/git/refs/heads/workspace-data"
        )
        == 2
    )
    assert calls.count("POST /repos/EPF-MDE/complex-web-services/git/trees") == 2


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
        "EPF-MDE/complex-web-services",
        lambda: "token",
        client=httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(handle)
        ),
    )
    assert data.read("roster.csv") == b"github_login\r\n"
    assert data.read("fork-readings/nobody.json") is None
