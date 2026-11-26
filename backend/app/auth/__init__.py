from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol, cast
from urllib.parse import urlencode

import httpx
import itsdangerous
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp

from app.roster import RosterSource, Student
from app.store import StoreUnavailable

logger = logging.getLogger(__name__)

SESSION_ID = "github_id"
SESSION_STATE = "oauth_state"
SESSION_REFUSED = "refused_login"
SESSION_IDLE_LIMIT = timedelta(days=60)

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
    def authorize_url(self, state: str, redirect_uri: str, request: Request) -> str: ...

    def identify(self, code: str, redirect_uri: str) -> GitHubUser: ...


class GitHubIdentity:
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
    pass


def _roster(request: Request) -> RosterSource:
    return cast(RosterSource, request.app.state.roster)


def _identity(request: Request) -> Identity:
    return cast(Identity, request.app.state.identity)


def _callback_url(request: Request) -> str:
    public_url = cast(str, request.app.state.settings.public_url)
    return public_url.rstrip("/") + "/auth/callback"


def _open_record(request: Request, student: Student) -> None:
    try:
        request.app.state.store.open_record(student)
    except StoreUnavailable as error:
        logger.warning(
            "Record of %s not opened at sign-in: %s", student.github_login, error
        )


class _ClockSigner(itsdangerous.TimestampSigner):
    def __init__(self, secret: str, clock: Callable[[], datetime]) -> None:
        super().__init__(secret)
        self._clock = clock

    def get_timestamp(self) -> int:
        return int(self._clock().timestamp())


class _ClockSessionMiddleware(SessionMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        /,
        secret_key: str,
        clock: Callable[[], datetime],
        **options: Any,
    ) -> None:
        super().__init__(app, secret_key=secret_key, **options)
        self.signer = _ClockSigner(secret_key, clock)


def add_session(
    app: FastAPI, secret: str, https_only: bool, clock: Callable[[], datetime]
) -> None:
    app.add_middleware(
        _ClockSessionMiddleware,
        secret_key=secret or secrets.token_urlsafe(32),
        clock=clock,
        session_cookie="cws_session",
        max_age=int(SESSION_IDLE_LIMIT.total_seconds()),
        same_site="lax",
        https_only=https_only,
    )


def current_student(request: Request) -> Student:
    github_id = request.session.get(SESSION_ID)
    student = (
        _roster(request).current().find(github_id) if github_id is not None else None
    )
    if student is None:
        request.session.pop(SESSION_ID, None)
        raise HTTPException(401, "Not signed in")
    request.session[SESSION_ID] = student.github_id
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
    evidence_project: str | None


router = APIRouter()


@router.get("/api/sign-in", tags=["session"])
def sign_in_page() -> SignInPage:
    return SignInPage(sign_in_url="/auth/login", notice=NOTICE)


@router.get("/api/sign-in/refusal", tags=["session"])
def refusal(request: Request) -> Refusal:
    login = request.session.get(SESSION_REFUSED)
    if login is None:
        raise HTTPException(404, "No refused sign-in")
    return Refusal(github_login=login, message=REFUSAL.format(login=login))


@router.get("/api/me", tags=["session"])
def me(student: Student = Depends(current_student)) -> Me:
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
