import json

import httpx
from conftest import MakeClient
from courses_under_test import OnTheRoster

from app.auth import GitHubIdentity


def fake_github(seen: list[tuple[str, str]], github_id: int) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path == "/login/oauth/access_token":
            assert b"code=the-code" in request.content
            return httpx.Response(200, json={"access_token": "ghu_student"})
        if request.url.path == "/user":
            assert request.headers["Authorization"] == "Bearer ghu_student"
            return httpx.Response(200, json={"id": github_id, "login": "renamed"})
        if request.method == "DELETE":
            assert json.loads(request.content) == {"access_token": "ghu_student"}
            return httpx.Response(204)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_github_sign_in_finds_the_student_by_id_and_revokes_the_token(
    make_client: MakeClient, student: OnTheRoster
) -> None:
    seen: list[tuple[str, str]] = []
    http = fake_github(seen, student.github_id)
    client = make_client(identity=GitHubIdentity("client-id", "client-secret", http))

    to_github = client.get("/auth/login", follow_redirects=False)
    assert to_github.headers["location"].startswith(
        "https://github.com/login/oauth/authorize?client_id=client-id"
    )
    state = httpx.URL(to_github.headers["location"]).params["state"]
    assert "scope" not in to_github.headers["location"]

    client.get("/auth/callback", params={"code": "the-code", "state": state})

    assert client.get("/api/me").json()["name"] == student.name
    assert ("DELETE", "/applications/client-id/token") in seen
