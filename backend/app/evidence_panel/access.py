from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx

from app.github_app import API, HEADERS, InstallationAuth, private_key_from_base64
from app.roster import Repository
from app.store import GITHUB, GITLAB, Host

from .panel import GITLAB_ACCESS, NOT_READABLE_ACCESS, READABLE_ACCESS, Access

GITLAB_MESSAGE = (
    "On GitLab, the workspace cannot check access: give the Instructor Reporter access."
)
GITLAB_HOW_TO_MAKE_READABLE = (
    "In your GitLab project: Manage, then Members, then Invite members. Invite the "
    "Instructor with the role "
    "Reporter (read-only). A public project needs nothing."
)
READABLE_MESSAGE = (
    "Readable: the course GitHub App can read `{repository}`. "
    "Only access was checked, never the contents."
)
YOUR_EVIDENCE_PROJECT = "Your Evidence Project: the Reading Day reads it in any case."
NOT_READABLE_MESSAGE = "Not readable yet: grant read-only access."
NOT_CHECKED_MESSAGE = (
    "Not readable yet, as far as the workspace can tell: it could not check access "
    "just now. "
    "Grant read-only access, then press Check again."
)


def github_how_to_make_readable(app_slug: str, name: str) -> str:
    where = (
        f"https://github.com/apps/{app_slug}/installations/new"
        if app_slug
        else "the course GitHub App's page"
    )
    return (
        f"Install the course GitHub App on this repository, read-only: open {where}, "
        "choose the account "
        f"that owns it, then “Only select repositories” and pick `{name}`. It asks for "
        "read access only. "
        "Then press Check again."
    )


class Readability(StrEnum):
    READABLE = "readable"
    NOT_READABLE = "not-readable"
    NOT_CHECKED = "not-checked"


def _readable_if(readable: bool) -> Readability:
    return Readability.READABLE if readable else Readability.NOT_READABLE


class NotAProject(ValueError):
    pass


@dataclass(frozen=True)
class Project:
    host: Host
    repository: Repository

    @property
    def url(self) -> str:
        return f"https://{self.host}.com/{self.repository}"

    @property
    def name(self) -> str:
        return self.repository.rsplit("/", 1)[-1]


_SEGMENT = re.compile(r"^[\w.-]+$")


def parse_project(url: str) -> Project:
    m = re.match(r"^https://(?:www\.)?(github|gitlab)\.com/([^?#]+)", url.strip())
    if not m:
        raise NotAProject(
            "Give the address of a repository on GitHub or GitLab, starting with https://"
        )
    host, path = m.group(1), m.group(2)
    parts = [p for p in path.split("/") if p]
    if host == GITHUB:
        parts = parts[:2]
    elif "-" in parts:
        parts = parts[: parts.index("-")]
    if len(parts) < 2 or not all(_SEGMENT.match(p) for p in parts):
        raise NotAProject(
            "Give the address of a repository: https://github.com/<owner>/<repository>"
        )
    parts[-1] = parts[-1].removesuffix(".git")
    return Project(host, Repository("/".join(parts)))  # type: ignore[arg-type]


def is_roster_evidence_project(
    repository: Repository, evidence_project: Repository | None
) -> bool:
    return (
        evidence_project is not None and repository.lower() == evidence_project.lower()
    )


class AccessCheck(Protocol):
    def can_read(self, repository: Repository) -> Readability: ...


def access(
    project: Project,
    evidence_project: Repository | None,
    check: AccessCheck,
    app_slug: str,
) -> Access:
    if project.host == GITLAB:
        return Access(
            status=GITLAB_ACCESS,
            message=GITLAB_MESSAGE,
            how_to_make_readable=GITLAB_HOW_TO_MAKE_READABLE,
        )
    if is_roster_evidence_project(project.repository, evidence_project):
        return Access(
            status=READABLE_ACCESS,
            message=YOUR_EVIDENCE_PROJECT,
            how_to_make_readable=None,
        )
    readability = check.can_read(project.repository)
    if readability == Readability.READABLE:
        return Access(
            status=READABLE_ACCESS,
            message=READABLE_MESSAGE.format(repository=project.repository),
            how_to_make_readable=None,
        )
    return Access(
        status=NOT_READABLE_ACCESS,
        message=NOT_READABLE_MESSAGE
        if readability == Readability.NOT_READABLE
        else NOT_CHECKED_MESSAGE,
        how_to_make_readable=github_how_to_make_readable(app_slug, project.name),
    )


@dataclass(frozen=True)
class _AccessAnswer:
    asked_at: float
    readability: Readability


class AppAccessCheck:
    TTL = 60.0

    def __init__(
        self,
        app_id: str,
        private_key_base64: str,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._app_id = app_id
        self._key = (
            private_key_from_base64(private_key_base64) if private_key_base64 else ""
        )
        self._client = client or httpx.Client(base_url=API, headers=HEADERS, timeout=10)
        self._clock = clock
        self._seen: dict[str, _AccessAnswer] = {}
        self._lock = threading.Lock()

    def can_read(self, repository: Repository) -> Readability:
        with self._lock:
            seen = self._seen.get(repository.lower())
        if seen and self._clock() - seen.asked_at < self.TTL:
            return seen.readability
        answer = self._ask(repository)
        with self._lock:
            self._seen[repository.lower()] = _AccessAnswer(self._clock(), answer)
        return answer

    def _ask(self, repository: Repository) -> Readability:
        if not (self._app_id and self._key):
            return Readability.NOT_CHECKED
        try:
            app_jwt = InstallationAuth(self._app_id, self._key, "").app_jwt()
            installed = self._client.get(
                f"/repos/{repository}/installation",
                headers={"Authorization": f"Bearer {app_jwt}"},
            )
            if installed.status_code == 200:
                return Readability.READABLE
            if installed.status_code != 404:
                return Readability.NOT_CHECKED
            public = self._client.get(f"/repos/{repository}")
            if public.status_code == 200:
                return _readable_if(not public.json().get("private", True))
            if public.status_code == 404:
                return Readability.NOT_READABLE
            return Readability.NOT_CHECKED
        except (httpx.HTTPError, ValueError):
            return Readability.NOT_CHECKED


class FakeAccessCheck:
    def __init__(self, readable: set[str] | None = None):
        self.rule: Callable[[str], Readability]
        if readable is None:
            self.rule = lambda repo: _readable_if("private" not in repo.lower())
        else:
            known = {r.lower() for r in readable}
            self.rule = lambda repo: _readable_if(repo.lower() in known)
        self.checked: list[str] = []

    def can_read(self, repository: Repository) -> Readability:
        self.checked.append(repository)
        return self.rule(repository)
