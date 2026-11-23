from pathlib import Path

import pytest
from conftest import (
    ADA_OF_OCEENS,
    GRACE_OF_MATHUTRICE,
    MakeClient,
    fixture_roster,
    sign_in,
)
from fastapi.testclient import TestClient

from app.auth import FakeIdentity
from app.main import ConfigurationError
from app.settings import Settings


def test_a_visitor_is_not_signed_in(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401


def test_a_student_on_the_roster_signs_in_and_lands_on_the_opening(
    client: TestClient,
) -> None:
    response = sign_in(client, ADA_OF_OCEENS)

    assert response.url.path == "/"
    me = client.get("/api/me").json()
    assert me == {
        "github_id": ADA_OF_OCEENS,
        "github_login": "ada-oceens",
        "name": "Ada Lovelace",
        "group": "OcéENS",
        "evidence_project": "ada-oceens/OceENS",
    }


def test_the_group_is_the_one_on_the_roster(client: TestClient) -> None:
    sign_in(client, GRACE_OF_MATHUTRICE)

    assert client.get("/api/me").json()["group"] == "MATHutrice"


def test_a_renamed_account_still_gets_in(make_client: MakeClient) -> None:
    client = make_client(identity=FakeIdentity(logins={ADA_OF_OCEENS: "ada-renamed"}))

    sign_in(client, ADA_OF_OCEENS)

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Ada Lovelace"


def test_a_login_on_the_roster_with_another_id_does_not_get_in(
    make_client: MakeClient,
) -> None:
    client = make_client(identity=FakeIdentity(logins={4242: "ada-oceens"}))

    response = sign_in(client, 4242)

    assert response.url.path == "/not-on-the-list"
    assert client.get("/api/me").status_code == 401


def test_someone_not_on_the_roster_is_told_so_and_whom_to_ask(
    client: TestClient,
) -> None:
    response = sign_in(client, 999)

    assert response.url.path == "/not-on-the-list"
    refusal = client.get("/api/sign-in/refusal").json()
    assert refusal["github_login"] == "user-999"
    assert "not on the Course's list" in refusal["message"]
    assert "Instructor" in refusal["message"]
    assert client.get("/api/me").status_code == 401


def test_the_session_persists_across_requests(client: TestClient) -> None:
    sign_in(client, ADA_OF_OCEENS)

    assert client.get("/api/me").status_code == 200
    assert client.get("/api/me").status_code == 200


def test_signing_out_ends_the_session(client: TestClient) -> None:
    sign_in(client, ADA_OF_OCEENS)

    client.post("/auth/logout")

    assert client.get("/api/me").status_code == 401


def test_a_student_removed_from_the_roster_is_signed_out(
    make_client: MakeClient, roster_csv: str
) -> None:
    from app.roster import StaticRoster

    roster = StaticRoster(fixture_roster(roster_csv))
    client = make_client(roster=roster)
    sign_in(client, ADA_OF_OCEENS)

    roster.replace(
        fixture_roster(roster_csv.replace("ada-oceens,1001", "ada-oceens,7777"))
    )

    assert client.get("/api/me").status_code == 401


def test_a_callback_without_the_state_it_was_sent_is_refused(
    client: TestClient,
) -> None:
    response = client.get(
        "/auth/callback",
        params={"code": f"fake-{ADA_OF_OCEENS}", "state": "forged"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert client.get("/api/me").status_code == 401


def test_the_sign_in_page_says_what_is_stored_where_who_reads_it(
    client: TestClient,
) -> None:
    page = client.get("/api/sign-in").json()

    assert page["sign_in_url"] == "/auth/login"
    notice = page["notice"]
    for words in ("GitHub", "United States", "Instructor", "deleted", "verdict"):
        assert words in notice


def test_a_roster_naming_a_group_the_course_does_not_hold_refuses_start(
    make_client: MakeClient, test_settings: Settings, roster_csv: str, tmp_path: Path
) -> None:
    roster = tmp_path / "roster.csv"
    roster.write_text(
        roster_csv.replace("Ada Lovelace,OcéENS,", "Ada Lovelace,OceENS,"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="OceENS"):
        make_client(
            settings=test_settings.model_copy(update={"roster_file": str(roster)})
        )
