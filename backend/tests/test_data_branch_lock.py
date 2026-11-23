import threading
import time

import httpx
from fake_github import FakeGitHub

from app.github_app import data_branch_lock
from app.repository_reading import GitHubWorkspaceData
from app.roster import Repository, Student
from app.store import GitHubStore

STUDENT = Student(
    1001,
    "ada-oceens",
    "Ada Lovelace",
    "OcéENS",
    "OcéENS",
    Repository("ada-oceens/OceENS"),
)


def test_every_writer_of_one_branch_gets_the_same_lock_and_other_branches_their_own() -> (  # noqa: E501
    None
):
    assert data_branch_lock(
        "EPF-MDE/complex-web-services", "workspace-data"
    ) is data_branch_lock("EPF-MDE/complex-web-services", "workspace-data")
    assert data_branch_lock(
        "EPF-MDE/complex-web-services", "workspace-data"
    ) is not data_branch_lock("EPF-MDE/complex-web-services", "other")


def is_git_data_api_call(request: httpx.Request) -> bool:
    return "/git/" in request.url.path


def test_a_drawing_and_a_repository_reading_write_one_at_a_time() -> None:
    github = FakeGitHub()
    log: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if is_git_data_api_call(request):
            log.append("reading")
            time.sleep(0.02)
            if request.method == "GET" and "/git/ref/" in path:
                return httpx.Response(200, json={"object": {"sha": "head"}})
            if request.method == "GET":
                return httpx.Response(200, json={"tree": {"sha": "tree"}})
            if request.method == "PATCH":
                return httpx.Response(200, json={})
            return httpx.Response(201, json={"sha": "new"})
        if request.method == "PUT":
            log.append("drawing")
            time.sleep(0.05)
        return github.handle(request)

    client = httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handle)
    )
    store = GitHubStore(client, github.repository, sleep=lambda seconds: None)
    data = GitHubWorkspaceData(github.repository, lambda: "token", client=client)
    store.open_record(STUDENT)

    drawing = threading.Thread(
        target=store.save_drawing,
        args=(STUDENT, "C1", "redraw", b"\x89PNG", {"document": {}}),
    )
    drawing.start()
    while "drawing" not in log:
        time.sleep(0.001)
    data.write(
        {"repository-readings/ada.json": b"{}"}, "data: read the repository of ada"
    )
    drawing.join()

    assert log[:2] == [
        "drawing",
        "drawing",
    ]
    assert set(log[2:]) == {"reading"}
