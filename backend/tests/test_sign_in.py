"""Signing in: GitHub says who you are, the roster says whether you get in.

Through the HTTP API only, with GitHub replaced by `FakeIdentity`.
"""

from conftest import ADA, GRACE, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.auth import FakeIdentity


def test_a_visitor_is_not_signed_in(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401


def test_a_student_on_the_roster_signs_in_and_lands_on_the_opening(
    client: TestClient,
) -> None:
    response = sign_in(client, ADA)

    assert response.url.path == "/"
    me = client.get("/api/me").json()
    assert me == {
        "github_id": ADA,
        "github_login": "ada-oceens",
        "name": "Ada Lovelace",
        "group": "OcéENS",
        "project": "OcéENS",
        "fork": "ada-oceens/OceENS",
    }


def test_the_project_is_the_one_on_the_roster(client: TestClient) -> None:
    sign_in(client, GRACE)

    assert client.get("/api/me").json()["project"] == "MATHutrice"


def test_a_renamed_account_still_gets_in(make_client: MakeClient) -> None:
    client = make_client(identity=FakeIdentity(logins={ADA: "ada-renamed"}))

    sign_in(client, ADA)

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Ada Lovelace"


def test_a_login_on_the_roster_with_another_id_does_not_get_in(
    make_client: MakeClient,
) -> None:
    # Someone who took over the login "ada-oceens" after Ada renamed hers.
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
    sign_in(client, ADA)

    assert client.get("/api/me").status_code == 200
    assert client.get("/api/me").status_code == 200


def test_signing_out_ends_the_session(client: TestClient) -> None:
    sign_in(client, ADA)

    client.post("/auth/logout")

    assert client.get("/api/me").status_code == 401


def test_a_student_removed_from_the_roster_is_signed_out(
    make_client: MakeClient, roster_csv: str
) -> None:
    from app.roster import StaticRoster, parse_roster

    roster = StaticRoster(parse_roster(roster_csv))
    client = make_client(roster=roster)
    sign_in(client, ADA)

    roster.replace(
        parse_roster(roster_csv.replace("ada-oceens,1001", "ada-oceens,7777"))
    )

    assert client.get("/api/me").status_code == 401


def test_a_callback_without_the_state_it_was_sent_is_refused(
    client: TestClient,
) -> None:
    response = client.get(
        "/auth/callback",
        params={"code": f"fake-{ADA}", "state": "forged"},
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


def test_a_roster_with_a_group_spelt_otherwise_is_refused(roster_csv: str) -> None:
    import pytest

    from app.roster import RosterError, parse_roster

    with pytest.raises(RosterError, match="OceENS"):
        parse_roster(roster_csv.replace("Ada Lovelace,OcéENS,", "Ada Lovelace,OceENS,"))
