"""Signing in with GitHub, checked against the roster.

GitHub (through the EPF-MDE CWS Student Connector, a GitHub App asking no
repository permission at sign-in) says who the visitor is: a numeric id and a
login. The roster says whether they get in. The session cookie then holds the
numeric id alone, and every request finds the Student on the current roster
again, so removing a row from roster.csv signs that person out.

The seam is `Identity`: `GitHubIdentity` in every deployed app, `FakeIdentity`
in tests and the local Playwright path, where `/auth/login?github_id=<id>`
signs that id in through the same callback.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.roster import RosterSource, Student
from app.store import StoreUnavailable

logger = logging.getLogger(__name__)

SESSION_ID = "github_id"
SESSION_STATE = "oauth_state"
SESSION_REFUSED = "refused_login"

NOTICE = (
    "What you send here (your answers, drawings, Self-assessment, Evidence Plan "
    "and questions) is stored on GitHub, in the United States, in a private "
    "repository only the Instructor reads, and it is deleted after the verdict."
)
REFUSAL = (
    "You are not on the Course's list. Ask the Instructor to add you, and give "
    "them your GitHub login: {login}."
)


@dataclass(frozen=True)
class GitHubUser:
    github_id: int
    login: str


class Identity(Protocol):
    """Who the visitor is, according to GitHub."""

    def authorize_url(self, state: str, redirect_uri: str, request: Request) -> str: ...

    def identify(self, code: str, redirect_uri: str) -> GitHubUser: ...


class GitHubIdentity:
    """GitHub's web flow, as the Student Connector App.

    The user token is used once, to read `GET /user`, then revoked: the app
    keeps no token of the Student's.
    """

    def __init__(
        self, client_id: str, client_secret: str, http: httpx.Client | None = None
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http or httpx.Client(timeout=20)

    def authorize_url(self, state: str, redirect_uri: str, request: Request) -> str:
        query = urlencode(
            {"client_id": self._client_id, "redirect_uri": redirect_uri, "state": state}
        )
        return f"https://github.com/login/oauth/authorize?{query}"

    def identify(self, code: str, redirect_uri: str) -> GitHubUser:
        exchanged = self._http.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        exchanged.raise_for_status()
        token = exchanged.json().get("access_token")
        if not token:
            raise SignInFailed(
                exchanged.json().get("error_description", "GitHub refused the code")
            )
        try:
            user = self._http.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            user.raise_for_status()
            body = user.json()
            return GitHubUser(github_id=int(body["id"]), login=body["login"])
        finally:
            self._http.request(
                "DELETE",
                f"https://api.github.com/applications/{self._client_id}/token",
                auth=(self._client_id, self._client_secret),
                json={"access_token": token},
                headers={"Accept": "application/vnd.github+json"},
            )


class FakeIdentity:
    """GitHub stood in for: `/auth/login?github_id=<id>` is that user.

    `logins` gives some ids another login than `user-<id>`, e.g. to rename an
    account. Never used by a deployed app (app.main refuses it on Azure).
    """

    def __init__(self, logins: dict[int, str] | None = None):
        self._logins = logins or {}

    def authorize_url(self, state: str, redirect_uri: str, request: Request) -> str:
        github_id = request.query_params.get("github_id", "")
        if not github_id.isdigit():
            raise HTTPException(400, "Fake sign-in: pass ?github_id=<numeric id>")
        return (
            f"{redirect_uri}?{urlencode({'code': f'fake-{github_id}', 'state': state})}"
        )

    def identify(self, code: str, redirect_uri: str) -> GitHubUser:
        github_id = int(code.removeprefix("fake-"))
        return GitHubUser(github_id, self._logins.get(github_id, f"user-{github_id}"))


class SignInFailed(Exception):
    """GitHub did not say who the visitor is."""


def _roster(request: Request) -> RosterSource:
    return cast(RosterSource, request.app.state.roster)


def _identity(request: Request) -> Identity:
    return cast(Identity, request.app.state.identity)


def _callback_url(request: Request) -> str:
    public_url = cast(str, request.app.state.settings.public_url)
    return public_url.rstrip("/") + "/auth/callback"


def _open_record(request: Request, student: Student) -> None:
    """The Store opens the Student's record at their first sign-in (their issue, on
    GitHub).

    If GitHub fails here the Student still signs in: their first send opens it.
    """
    try:
        request.app.state.store.open_record(student)
    except StoreUnavailable as error:
        logger.warning(
            "Record of %s not opened at sign-in: %s", student.github_login, error
        )


def current_student(request: Request) -> Student:
    """The signed-in Student, as on the roster now; 401 otherwise."""
    github_id = request.session.get(SESSION_ID)
    student = (
        _roster(request).current().find(github_id) if github_id is not None else None
    )
    if student is None:
        request.session.pop(SESSION_ID, None)
        raise HTTPException(401, "Not signed in")
    return student


class SignInPage(BaseModel):
    sign_in_url: str
    notice: str


class Refusal(BaseModel):
    github_login: str
    message: str


class Me(BaseModel):
    github_id: int
    github_login: str
    name: str
    group: str
    project: str
    evidence_project: str


router = APIRouter()


@router.get("/api/sign-in", tags=["session"])
def sign_in_page() -> SignInPage:
    """What the sign-in page says before the Student signs in."""
    return SignInPage(sign_in_url="/auth/login", notice=NOTICE)


@router.get("/api/sign-in/refusal", tags=["session"])
def refusal(request: Request) -> Refusal:
    """Why the last sign-in was refused: not on the roster."""
    login = request.session.get(SESSION_REFUSED)
    if login is None:
        raise HTTPException(404, "No refused sign-in")
    return Refusal(github_login=login, message=REFUSAL.format(login=login))


@router.get("/api/me", tags=["session"])
def me(student: Student = Depends(current_student)) -> Me:
    """The signed-in Student, with their Group and Project from the roster."""
    return Me(**student.as_dict())


@router.get("/auth/login", include_in_schema=False)
def login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    request.session[SESSION_STATE] = state
    return RedirectResponse(
        _identity(request).authorize_url(state, _callback_url(request), request)
    )


@router.get("/auth/callback", include_in_schema=False)
def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    expected = request.session.pop(SESSION_STATE, None)
    if not code or not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(
            400, "This sign-in link has expired: start again from the sign-in page."
        )
    user = _identity(request).identify(code, _callback_url(request))
    request.session.pop(SESSION_ID, None)
    student = _roster(request).current().find(user.github_id)
    if student is None:
        request.session[SESSION_REFUSED] = user.login
        logger.warning(
            "Sign-in refused: GitHub user %s (id %s) is not on the roster",
            user.login,
            user.github_id,
        )
        return RedirectResponse("/not-on-the-list", status_code=303)
    request.session.pop(SESSION_REFUSED, None)
    request.session[SESSION_ID] = user.github_id
    logger.info("Signed in: GitHub user %s (id %s)", user.login, user.github_id)
    _open_record(request, student)
    return RedirectResponse("/", status_code=303)


@router.post("/auth/logout", include_in_schema=False)
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/sign-in", status_code=303)
