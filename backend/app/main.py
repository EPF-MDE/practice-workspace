"""The Rehearsal workspace: one FastAPI app, serving its API and its React build.

`create_app()` assembles the pieces; `app` is the instance uvicorn runs
(`uvicorn app.main:app`, one worker: the Store serialises its writes in-process).
Later tickets add their router here and their seam as a keyword argument.
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import auth, observability, rehearsal
from app.auth import FakeIdentity, GitHubIdentity, Identity
from app.content import load_content
from app.evidence_panel import (
    AccessCheck,
    AppAccessCheck,
    FakeAccessCheck,
    LazyRepositoryReadingSource,
    OfflineRepositoryReading,
    RepositoryReadingSource,
)
from app.github_app import installation_client, read_file
from app.repository_reading import (
    DirectoryReadings,
    GitHubWorkspaceData,
    HttpGitHub,
    RepositoryReader,
    WorkspaceDataReadings,
    installation_token,
)
from app.roster import RefreshingRoster, RosterSource, StaticRoster
from app.settings import Settings, get_settings
from app.store import GitHubStore, InMemoryStore, SendTooLarge, Store, StoreUnavailable

logger = logging.getLogger("app")

BACKEND = Path(__file__).resolve().parents[1]
# The React build: copied here by the artefact build, or built in place locally.
STATIC_CANDIDATES = (BACKEND / "static", BACKEND.parent / "frontend" / "dist")
# The commit the artefact was built from, written by the build; "unknown" locally.
REVISION_FILE = BACKEND / "REVISION"
# The fake Repository reading's readings, for local runs and Playwright (not in the
# artefact).
FAKE_REPOSITORY_READINGS = BACKEND / "tests" / "fixtures"
# What a Student reads when GitHub, behind the Store, fails (503).
STORE_UNAVAILABLE = (
    "GitHub, where the workspace stores your work, did not answer. "
    "Nothing was lost: what you typed is still in this browser. Wait a minute and try "
    "again."
)
# What a Student reads when a send is too large for the Store (422): retrying would not
# help.
SEND_TOO_LARGE = (
    "This send is too long to store: shorten your text (or remove unusual characters "
    "pasted into it), "
    "then send again. What you typed is still in this browser."
)
# Session cookie lifetime: past the Reading Day, so a session lasts the course.
SESSION_MAX_AGE = 60 * 60 * 24 * 60


class ConfigurationError(RuntimeError):
    """Settings the app refuses to run with."""


def _on_azure() -> bool:
    return bool(os.environ.get("WEBSITE_SITE_NAME"))


def _revision() -> str:
    return REVISION_FILE.read_text().strip() if REVISION_FILE.exists() else "unknown"


def default_roster(settings: Settings) -> RosterSource:
    if settings.roster_file:
        return StaticRoster.from_file(settings.roster_file)
    client = installation_client(
        settings.store_app_id,
        settings.store_app_private_key_base64,
        settings.store_app_installation_id,
    )
    return RefreshingRoster(
        lambda: read_file(
            client, settings.repository, settings.data_branch, "roster.csv"
        )
    )


def default_identity(settings: Settings) -> Identity:
    if settings.sign_in == "fake":
        return FakeIdentity()
    return GitHubIdentity(
        settings.github_app_client_id, settings.github_app_client_secret
    )


def default_content_dir(settings: Settings) -> Path:
    """The Course folder, only ever from WORKSPACE_CONTENT_DIR: the engine
    holds no course of its own."""
    if not settings.content_dir:
        raise ConfigurationError("No content folder: set WORKSPACE_CONTENT_DIR")
    return Path(settings.content_dir)


def default_store(settings: Settings) -> Store:
    if settings.store == "memory":
        if _on_azure():
            logger.warning(
                "WORKSPACE_STORE=memory: every send is lost when the app restarts"
            )
        return InMemoryStore()
    client = installation_client(
        settings.store_app_id,
        settings.store_app_private_key_base64,
        settings.store_app_installation_id,
    )
    # Only the Store App's own comments are sends; its slug defaults to the course's
    # App.
    bot: dict[str, Any] = (
        {"bot_login": f"{settings.store_app_slug}[bot]"}
        if settings.store_app_slug
        else {}
    )
    return GitHubStore(
        client,
        settings.repository,
        label=settings.store_label,
        data_branch=settings.data_branch,
        **bot,
    )


def _fake_repository_reading(settings: Settings) -> bool:
    if settings.repository_reading == "auto":
        return settings.sign_in == "fake"
    return settings.repository_reading == "fake"


def default_repository_reading(settings: Settings) -> RepositoryReadingSource:
    if _fake_repository_reading(settings):
        folder = (
            Path(settings.repository_readings_dir)
            if settings.repository_readings_dir
            else FAKE_REPOSITORY_READINGS
        )
        return OfflineRepositoryReading(
            DirectoryReadings(folder) if folder.is_dir() else None
        )

    def build() -> RepositoryReadingSource:
        # Raises until the Student Connector has an installation: the panel then says
        # the repository could not be read now, and the next view tries again.
        token = installation_token(
            settings.github_app_id,
            settings.github_app_private_key_base64,
            settings.github_app_installation_id,
        )
        store_token = installation_token(
            settings.store_app_id,
            settings.store_app_private_key_base64,
            settings.store_app_installation_id,
        )
        data = GitHubWorkspaceData(
            settings.repository, store_token, branch=settings.data_branch
        )
        return RepositoryReader(HttpGitHub(token), WorkspaceDataReadings(data))

    return LazyRepositoryReadingSource(build)


def default_access_check(settings: Settings) -> AccessCheck:
    if _fake_repository_reading(settings):
        return FakeAccessCheck()
    return AppAccessCheck(
        settings.github_app_id, settings.github_app_private_key_base64
    )


def create_app(
    settings: Settings | None = None,
    roster: RosterSource | None = None,
    identity: Identity | None = None,
    store: Store | None = None,
    repository_reading: RepositoryReadingSource | None = None,
    access_check: AccessCheck | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if _on_azure():
        if settings.sign_in != "github":
            raise ConfigurationError("WORKSPACE_SIGN_IN=fake is refused on Azure")
        if not settings.session_secret:
            raise ConfigurationError("WORKSPACE_SESSION_SECRET missing")
    observability.check_settings(
        settings.posthog_project_token,
        settings.posthog_host,
        settings.posthog_environment,
    )
    revision = _revision()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.signals = observability.start(
            "cws-workspace",
            settings.posthog_project_token,
            settings.posthog_host,
            settings.posthog_environment,
        )
        # The app's own INFO lines (sign-ins, start) reach PostHog Logs too.
        logging.getLogger("app").setLevel(logging.INFO)
        logger.info("cws-workspace %s started", revision)
        yield
        app.state.signals.shutdown()

    app = FastAPI(
        title="Rehearsal workspace",
        lifespan=lifespan,
        # "<tag>-<function>": the generated client's SessionService.me(), etc.
        generate_unique_id_function=lambda route: (
            f"{route.tags[0]}-{route.name}" if route.tags else route.name
        ),
    )
    app.state.settings = settings
    app.state.roster = roster or default_roster(settings)
    app.state.identity = identity or default_identity(settings)
    app.state.store = store if store is not None else default_store(settings)
    app.state.repository_reading = (
        repository_reading
        if repository_reading is not None
        else default_repository_reading(settings)
    )
    app.state.access_check = (
        access_check if access_check is not None else default_access_check(settings)
    )
    # Read and checked once: a content file the app refuses stops it at start.
    app.state.content = load_content(default_content_dir(settings))
    app.state.signals = observability.Signals()

    @app.middleware("http")
    async def errors_to_posthog(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Inside SessionMiddleware (added after), so the session is loaded.
        github_id = request.session.get(auth.SESSION_ID)
        with request.app.state.signals.request_context(
            str(github_id) if github_id else None, path=request.url.path
        ):
            response = await call_next(request)
        response.headers["X-Revision"] = revision
        return response

    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(
        request: Request, error: StoreUnavailable
    ) -> JSONResponse:
        logger.warning(
            "Store unavailable on %s %s: %s", request.method, request.url.path, error
        )
        return JSONResponse(
            {"detail": STORE_UNAVAILABLE},
            status_code=503,
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(SendTooLarge)
    async def send_too_large(request: Request, error: SendTooLarge) -> JSONResponse:
        logger.warning(
            "Send too large on %s %s: %s", request.method, request.url.path, error
        )
        return JSONResponse({"detail": SEND_TOO_LARGE}, status_code=422)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret or secrets.token_urlsafe(32),
        session_cookie="cws_session",
        max_age=SESSION_MAX_AGE,
        same_site="lax",
        https_only=settings.public_url.startswith("https://"),
    )

    app.include_router(auth.router)
    app.include_router(rehearsal.router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, Any]:
        """Answers once the app runs; the deploy waits for its revision."""
        return {"status": "ok", "revision": revision}

    @app.get("/api/health/error", include_in_schema=False)
    def error_check(key: str = "") -> None:
        if not settings.error_check_key or not secrets.compare_digest(
            key, settings.error_check_key
        ):
            raise HTTPException(404)
        raise RuntimeError(
            f"Error check on cws-workspace {revision}: raised on purpose"
        )

    _serve_frontend(app)
    return app


def _serve_frontend(app: FastAPI) -> None:
    """The React build on the same domain; any other path gets index.html."""
    static = next(
        (path for path in STATIC_CANDIDATES if (path / "index.html").exists()), None
    )
    if static is None:
        return
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "auth/")):
            raise HTTPException(404)
        file = (static / path).resolve()
        if path and file.is_file() and file.is_relative_to(static):
            return FileResponse(file)
        return FileResponse(static / "index.html")


def _app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    # `app.main:app` is built on first access, so importing create_app in tests
    # never reads the real settings or reaches GitHub.
    if name == "app":
        globals()["app"] = instance = _app()
        return instance
    raise AttributeError(name)
