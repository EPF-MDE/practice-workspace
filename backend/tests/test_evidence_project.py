from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from conftest import ADA, MakeClient, sign_in
from fake_github import FakeGitHub
from fastapi.testclient import TestClient

from app.evidence_panel import FakeAccessCheck, OfflineRepositoryReading, Readability
from app.settings import Settings
from app.store import GitHubStore, InMemoryStore, Store

C2 = "/api/competencies/C2"
DECLARATION = "/api/evidence-project/declaration"
CHECK = "/api/evidence-project/check"
BAKERY = {
    "url": "https://github.com/ada/bakery",
    "what_to_read": "The pipeline: .github/workflows, and pull request #4.",
}


@pytest.fixture
def access() -> FakeAccessCheck:
    return FakeAccessCheck(readable={"ada/bakery"})


@pytest.fixture
def ada(
    make_client: MakeClient, access: FakeAccessCheck, test_settings: Settings
) -> TestClient:
    settings = test_settings.model_copy(
        update={"github_app_slug": "cws-student-connector"}
    )
    client = make_client(
        settings=settings,
        repository_reading=OfflineRepositoryReading(),
        access_check=access,
    )
    sign_in(client, ADA)
    return client


def test_the_panel_tells_the_student_who_reads_a_declared_project_and_what_cannot_be_read(  # noqa: E501
    ada: TestClient,
) -> None:
    help = ada.get(f"{C2}/evidence-panel").json()["help"]

    assert help["notice"].startswith(
        "The Instructor and an AI tool (Mistral, which may train on what it reads)"
    )
    assert "keep your Evidence Project instead" in help["notice"]
    assert "behind a login" in help["password_example"]
    assert "in the repository itself" in help["documentation_advice"]


def test_a_readable_github_project_is_declared_once_for_every_competency(
    ada: TestClient, store: InMemoryStore
) -> None:
    before = store.writes

    declared = ada.post(DECLARATION, json=BAKERY).json()

    assert store.writes == before + 1
    assert declared["url"] == "https://github.com/ada/bakery"
    assert declared["what_to_read"] == BAKERY["what_to_read"]
    assert declared["access"]["status"] == "readable"
    for competency in ("C1", "C2", "C3"):
        panel = ada.get(f"/api/competencies/{competency}/evidence-panel").json()
        assert panel["declaration"]["repository"] == "ada/bakery"
        assert panel["evidence_project"] == "ada/bakery"
    page = ada.get("/api/competencies/C1").json()
    assert page["evidence_project"] == "https://github.com/ada/bakery"


def test_a_private_github_project_not_readable_yet_says_how_to_grant_read_only_access(
    ada: TestClient,
) -> None:
    declared = ada.post(
        DECLARATION,
        json={
            "url": "https://github.com/ada/secret/tree/main/docs",
            "what_to_read": "docs",
        },
    )

    access = declared.json()["access"]
    assert access["status"] == "not-readable"
    assert access["message"] == "Not readable yet: grant read-only access."
    assert (
        "https://github.com/apps/cws-student-connector/installations/new"
        in access["how_to_make_readable"]
    )
    assert "`secret`" in access["how_to_make_readable"]
    assert declared.json()["url"] == "https://github.com/ada/secret"


def test_access_is_checked_again_on_each_view_so_a_grant_shows_without_declaring_again(
    ada: TestClient, access: FakeAccessCheck
) -> None:
    ada.post(
        DECLARATION,
        json={"url": "https://github.com/ada/secret", "what_to_read": "docs"},
    )
    access.rule = lambda repo: Readability.READABLE

    assert (
        ada.get(f"{C2}/evidence-panel").json()["declaration"]["access"]["status"]
        == "readable"
    )


def test_when_access_cannot_be_checked_it_reads_not_readable_yet_and_says_why(
    ada: TestClient, access: FakeAccessCheck
) -> None:
    access.rule = lambda repo: Readability.NOT_CHECKED

    checked = ada.post(CHECK, json={"url": "https://github.com/ada/secret"}).json()

    assert checked["status"] == "not-readable"
    assert checked["message"].startswith("Not readable yet")
    assert "could not check access just now" in checked["message"]


def test_a_gitlab_project_is_told_to_give_the_instructor_reporter_access_and_is_not_checked(  # noqa: E501
    ada: TestClient, access: FakeAccessCheck
) -> None:
    declared = ada.post(
        DECLARATION,
        json={
            "url": "https://gitlab.com/epf/team/api/-/tree/main",
            "what_to_read": "the CI",
        },
    ).json()

    assert declared["repository"] == "epf/team/api"
    assert declared["access"]["status"] == "gitlab"
    assert declared["access"]["how_to_make_readable"]
    assert access.checked == []


def test_checking_access_before_declaring_stores_nothing(
    ada: TestClient, store: InMemoryStore, access: FakeAccessCheck
) -> None:
    before = store.writes

    checked = ada.post(CHECK, json={"url": "https://github.com/ada/bakery"})

    assert checked.json()["status"] == "readable"
    assert store.writes == before
    assert access.checked == ["ada/bakery"]


def test_declaring_the_rosters_evidence_project_reads_it_as_before(
    ada: TestClient,
) -> None:
    declared = ada.post(
        DECLARATION,
        json={"url": "https://github.com/ada-oceens/OceENS", "what_to_read": "all"},
    ).json()

    assert declared["declares_roster_evidence_project"] is True
    assert declared["access"]["status"] == "readable"
    assert ada.get(f"{C2}/evidence-panel").json()["evidence_project"] == (
        "ada-oceens/OceENS"
    )


@pytest.mark.parametrize(
    "sent",
    [
        {"url": "https://bitbucket.org/ada/bakery", "what_to_read": "x"},
        {"url": "github.com/ada/bakery", "what_to_read": "x"},
        {"url": "https://github.com/ada", "what_to_read": "x"},
        {"url": "https://github.com/ada/bakery", "what_to_read": "  "},
    ],
)
def test_a_declaration_needs_a_github_or_gitlab_repository_and_a_note(
    ada: TestClient, sent: dict[str, str], store: InMemoryStore
) -> None:
    before = store.writes
    assert ada.post(DECLARATION, json=sent).status_code == 422
    assert store.writes == before


def test_a_declaration_can_be_changed_then_withdrawn_back_to_the_rosters(
    ada: TestClient,
) -> None:
    ada.post(DECLARATION, json=BAKERY)
    changed = ada.post(
        DECLARATION,
        json={"url": "https://github.com/ada/oven", "what_to_read": "README"},
    ).json()
    assert changed["repository"] == "ada/oven"
    assert ada.get(f"{C2}/evidence-panel").json()["evidence_project"] == "ada/oven"

    withdrawn = ada.delete(DECLARATION)

    assert withdrawn.status_code == 200
    panel = ada.get(f"{C2}/evidence-panel").json()
    assert panel["declaration"] is None
    assert panel["evidence_project"] == "ada-oceens/OceENS"
    assert ada.delete(DECLARATION).status_code == 409


def test_a_declaration_changes_until_the_reading_day_and_no_later(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    def client(reading_day: datetime) -> TestClient:
        c = make_client(
            settings=test_settings.model_copy(
                update={"closes_at": past, "reading_day_at": reading_day}
            ),
            repository_reading=OfflineRepositoryReading(),
            access_check=FakeAccessCheck(),
        )
        sign_in(c, ADA)
        return c

    open_until_reading_day = client(future)
    assert open_until_reading_day.post(DECLARATION, json=BAKERY).status_code == 200

    over = client(past)
    assert over.post(DECLARATION, json=BAKERY).status_code == 403
    assert over.delete(DECLARATION).status_code == 403


C1 = "/api/competencies/C1"


def _rate_and_close(client: TestClient, **extra: Any) -> httpx.Response:
    client.post(
        f"{C1}/self-assessment",
        json={"levels": {"C1.a": {"level": "understand", "link": None}}},
    )
    response: httpx.Response = client.post(
        f"{C1}/close", json={"text": "My plan.", "example": "My README.", **extra}
    )
    return response


Counted = tuple[TestClient, Store, Callable[[], int]]


@pytest.fixture(params=["memory", "github"])
def counted(request: pytest.FixtureRequest, make_client: MakeClient) -> Counted:
    store: Store
    if request.param == "memory":
        store = InMemoryStore()
        writes = lambda: store.writes  # noqa: E731
    else:
        github = FakeGitHub()
        store = GitHubStore(github.client(), github.repository)
        writes = lambda: github.writes  # noqa: E731
    repositories = OfflineRepositoryReading()
    client = make_client(
        store=store, repository_reading=repositories, access_check=FakeAccessCheck()
    )
    sign_in(client, ADA)
    return client, store, writes


def test_the_closing_step_stores_the_panel_and_the_declaration_in_its_one_send(
    counted: Counted,
) -> None:
    client, store, writes = counted
    client.post(
        f"{C1}/self-assessment",
        json={"levels": {"C1.a": {"level": "understand", "link": None}}},
    )
    before = writes()

    closed = client.post(
        f"{C1}/close",
        json={"text": "My plan.", "example": "My README.", "declaration": BAKERY},
    )

    assert closed.status_code == 200
    assert writes() == before + 1
    panel = client.get("/api/competencies/C2/evidence-panel").json()
    assert panel["declaration"]["repository"] == "ada/bakery"
    assert panel["evidence_project"] == "ada/bakery"
    assert client.get(C1).json()["evidence_project"] == "https://github.com/ada/bakery"
    assert panel["declaration"]["what_to_read"] == BAKERY["what_to_read"]
    plan = client.get(C1).json()["evidence_plan"]
    assert (plan["confirmed"], plan["version"]) == (True, 1)


def test_closing_without_a_declaration_still_stores_the_panel(counted: Counted) -> None:
    client, store, writes = counted
    shown = client.get(f"{C1}/evidence-panel").json()
    before = writes()

    assert _rate_and_close(client).status_code == 200

    assert writes() == before + 2
    assert client.get(C1).json()["evidence_plan"]["confirmed"] is True
    assert client.get(C1).json()["evidence_project"] is None
    assert client.get(f"{C1}/evidence-panel").json()["read_at"] == shown["read_at"]
    assert client.get(f"{C1}/evidence-panel").json()["declaration"] is None


def test_a_declaration_after_the_closing_step_is_its_own_send_and_wins(
    counted: Counted,
) -> None:
    client, _, writes = counted
    _rate_and_close(client, declaration=BAKERY)
    before = writes()

    client.delete(DECLARATION)

    assert writes() == before + 1
    assert client.get(f"{C1}/evidence-panel").json()["declaration"] is None
    assert client.get(C1).json()["evidence_project"] is None


def test_the_closing_step_refuses_a_bad_declaration_and_stores_nothing(
    counted: Counted,
) -> None:
    client, _, writes = counted
    client.post(
        f"{C1}/self-assessment",
        json={"levels": {"C1.a": {"level": "understand", "link": None}}},
    )
    before = writes()

    refused = client.post(
        f"{C1}/close",
        json={
            "text": "p",
            "example": "e",
            "declaration": {"url": "https://example.com/x", "what_to_read": "n"},
        },
    )

    assert refused.status_code == 422
    assert writes() == before
