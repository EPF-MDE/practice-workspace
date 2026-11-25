from pathlib import Path

import pytest
from conftest import MakeClient, sign_in
from courses_under_test import CourseFolder, OnTheRoster
from fastapi.testclient import TestClient

from app.auth import FakeIdentity
from app.roster import RefreshingRoster, StaticRoster
from app.settings import ConfigurationError, Settings


def test_a_visitor_is_not_signed_in(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401


def test_a_student_on_the_roster_signs_in_and_lands_on_the_opening(
    client: TestClient, student: OnTheRoster
) -> None:
    response = sign_in(client, student.github_id)

    assert response.url.path == "/"
    me = client.get("/api/me").json()
    assert me == {
        "github_id": student.github_id,
        "github_login": student.github_login,
        "name": student.name,
        "group": student.group,
        "evidence_project": student.evidence_project,
    }


def test_the_group_is_the_one_on_the_roster(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)

        assert client.get("/api/me").json()["group"] == student.group


def test_a_renamed_account_still_gets_in(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    client = make_client(
        identity=FakeIdentity(logins={student.github_id: "a-renamed-login"})
    )

    sign_in(client, student.github_id)

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["name"] == student.name


def test_a_login_on_the_roster_with_another_id_does_not_get_in(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    client = make_client(identity=FakeIdentity(logins={4242: student.github_login}))

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


def test_the_session_persists_across_requests(signed_in: TestClient) -> None:
    assert signed_in.get("/api/me").status_code == 200
    assert signed_in.get("/api/me").status_code == 200


def test_signing_out_ends_the_session(signed_in: TestClient) -> None:
    signed_in.post("/auth/logout")

    assert signed_in.get("/api/me").status_code == 401


def test_a_student_removed_from_the_roster_is_signed_out(
    make_client: MakeClient, course: CourseFolder, student: OnTheRoster
) -> None:
    roster = StaticRoster(course.roster(course.roster_csv))
    client = make_client(roster=roster)
    sign_in(client, student.github_id)

    roster.replace(
        course.roster(
            course.roster_csv.replace(
                f"{student.github_login},{student.github_id},",
                f"{student.github_login},7777,",
            )
        )
    )

    assert client.get("/api/me").status_code == 401


def test_a_callback_without_the_state_it_was_sent_is_refused(
    client: TestClient, student: OnTheRoster
) -> None:
    response = client.get(
        "/auth/callback",
        params={"code": f"fake-{student.github_id}", "state": "forged"},
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


def with_an_unknown_group(course: CourseFolder, student: OnTheRoster) -> str:
    return course.roster_csv.replace(
        f"{student.name},{student.group},", f"{student.name},Not-a-Group,"
    )


def test_a_roster_naming_a_group_the_course_does_not_hold_refuses_start(
    make_client: MakeClient,
    test_settings: Settings,
    course: CourseFolder,
    student: OnTheRoster,
    tmp_path: Path,
) -> None:
    roster = tmp_path / "roster.csv"
    roster.write_text(with_an_unknown_group(course, student), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="line 2: the Group 'Not-a-Group'"):
        make_client(
            settings=test_settings.model_copy(update={"roster_file": str(roster)})
        )


def test_a_data_branch_roster_naming_a_group_the_course_does_not_hold_refuses_start(
    make_client: MakeClient, course: CourseFolder, student: OnTheRoster
) -> None:
    unknown_group = with_an_unknown_group(course, student)
    read_from_the_data_branch = RefreshingRoster(
        lambda: unknown_group, course.course.groups
    )

    with pytest.raises(ConfigurationError, match="line 2: the Group 'Not-a-Group'"):
        make_client(roster=read_from_the_data_branch)
