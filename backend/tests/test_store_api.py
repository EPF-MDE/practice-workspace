"""The Store as the API's clients see it: the write budget, the GitHub Store
behind the app, and a clear 503 when GitHub fails."""

from __future__ import annotations

import base64

import pytest
from conftest import ADA, Counted, MakeClient, sign_in
from fake_github import FakeGitHub

from app.main import default_store
from app.settings import Settings
from app.store import GitHubStore, InMemoryStore

PAGE = "/api/competencies/C1"
DRAWING = {
    "png_base64": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode(),
    "snapshot": {"document": {"store": {}, "schema": {}}, "session": {}},
}


@pytest.fixture(params=["memory", "github"])
def counted(request: pytest.FixtureRequest, make_client: MakeClient) -> Counted:
    """A client on either Store, and how many writes that Store has made so far."""
    if request.param == "memory":
        store = InMemoryStore()
        return make_client(store=store), lambda: store.writes
    github = FakeGitHub()
    return make_client(
        store=GitHubStore(github.client(), github.repository)
    ), lambda: github.writes


def test_a_full_competency_path_makes_at_most_10_writes_and_none_before_a_send(
    counted: Counted,
) -> None:
    client, writes = counted
    sign_in(
        client, ADA
    )  # the GitHub Store opens the Student's issue here, once per course
    after_sign_in = writes()

    page = client.get(PAGE).json()
    sign_in(client, ADA)
    client.get(PAGE)
    assert writes() == after_sign_in, "no write before a send"

    # The whole path: every step with fields answered (the Transfer included),
    # the redraw sent (not the optional one: 2 files and a comment), two
    # questions asked; then the closing step: the Self-assessment, carrying the
    # missed check points the browser kept, rated and drafted as the Student
    # goes; then one send confirming the Evidence Plan with an example for the
    # Eval (#468 adds the evidence panel snapshot to that same send).
    missed: dict[str, list[str]] = {}
    for step in page["steps"]:
        fields = [b["id"] for b in step["blocks"] if b["type"] == "field"]
        if fields:
            assert client.post(
                f"{PAGE}/steps/{step['id']}/answer",
                json={"fields": {f: "x" for f in fields}},
            ).is_success
        if step["kind"] == "drawing" and not step["optional"]:
            sent = client.post(
                f"{PAGE}/steps/{step['id']}/drawing", json=DRAWING
            ).json()
            missed[step["id"]] = [sent["reference"]["check_points"][0]["id"]]
        client.get(PAGE)
    for step in page["steps"][:2]:
        assert client.post(
            f"{PAGE}/steps/{step['id']}/questions", json={"text": "?"}
        ).is_success
    points = [
        b["id"] for s in page["steps"] for b in s["blocks"] if b["type"] == "point"
    ]
    rated: dict[str, dict[str, str | None]] = {}
    for point in points:
        rated[point] = {"level": "redo", "link": None}
        draft = client.post(
            f"{PAGE}/evidence-plan/draft", json={"levels": rated}
        ).json()["text"]
    assert client.post(
        f"{PAGE}/self-assessment", json={"levels": rated, "missed_check_points": missed}
    ).is_success
    assert client.post(
        f"{PAGE}/close", json={"text": draft, "example": "my README"}
    ).is_success

    assert writes() - after_sign_in <= 10


def test_the_first_sign_in_opens_the_students_issue_and_later_ones_do_not(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    client = make_client(store=GitHubStore(github.client(), github.repository))

    sign_in(client, ADA)
    sign_in(client, ADA)

    assert github.writes == 1
    assert len(github.issues) == 1


def test_sends_through_the_github_store_are_read_back_after_a_restart(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    client = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(client, ADA)
    client.post(
        f"{PAGE}/steps/the-number-changes/answer", json={"fields": {"what-moves": "D"}}
    )

    restarted = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(restarted, ADA)
    step = next(
        s
        for s in restarted.get(PAGE).json()["steps"]
        if s["id"] == "the-number-changes"
    )

    assert step["sent"]["fields"] == {"what-moves": "D"}


def test_a_drawing_sent_through_the_github_store_is_read_back_after_a_restart(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    client = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(client, ADA)
    client.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)

    restarted = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(restarted, ADA)

    assert (
        restarted.get(f"{PAGE}/steps/redraw/drawing").json()["snapshot"]
        == DRAWING["snapshot"]
    )
    page = restarted.get(PAGE).json()
    assert (
        next(s for s in page["steps"] if s["id"] == "redraw")["drawing"]["version"] == 1
    )


def test_when_github_fails_a_drawing_send_gets_a_clear_503(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    client = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(client, ADA)
    github.down = 502

    response = client.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]


def test_when_github_fails_a_send_gets_a_clear_503(make_client: MakeClient) -> None:
    github = FakeGitHub()
    client = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(client, ADA)
    github.down = 502

    response = client.post(
        f"{PAGE}/steps/the-number-changes/answer", json={"fields": {"what-moves": "D"}}
    )

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]


def test_when_github_fails_a_page_needing_the_record_gets_a_clear_503(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    github.down = 503
    client = make_client(store=GitHubStore(github.client(), github.repository))
    sign_in(client, ADA)

    response = client.get(PAGE)

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]


def test_when_github_fails_at_sign_in_the_student_still_signs_in(
    make_client: MakeClient,
) -> None:
    github = FakeGitHub()
    github.down = 503
    client = make_client(store=GitHubStore(github.client(), github.repository))

    sign_in(client, ADA)
    github.down = None

    assert client.get("/api/me").json()["github_id"] == ADA


def test_the_store_is_a_setting(test_settings: Settings) -> None:
    assert isinstance(default_store(test_settings), InMemoryStore)
    github = default_store(
        test_settings.model_copy(
            update={
                "store": "github",
                "store_label": "rehearsal-staging",
                "store_app_id": "1",
                "store_app_private_key_base64": "LS0t",
                "store_app_installation_id": "2",
            }
        )
    )
    assert isinstance(github, GitHubStore)
