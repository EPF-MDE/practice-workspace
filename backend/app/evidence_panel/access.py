"""Evidence Project declarations: the project URL, and whether the Reading Day can read
it.

Only access is checked, never contents. A GitHub repository is readable when
it is public, or when the course GitHub App (the Student Connector) is
installed on it; GitLab gets no automatic check, only the instruction to give
the Instructor Reporter access.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.github_app import API, HEADERS, InstallationAuth, private_key_from_base64
from app.store import GITHUB, GITLAB, Host

from .panel import GITLAB_ACCESS, NOT_READABLE_ACCESS, READABLE_ACCESS, Access

GITLAB_MESSAGE = (
    "On GitLab, the workspace cannot check access: give the Instructor Reporter access."
)
GITLAB_HOW = (
    "In your GitLab project: Manage, then Members, then Invite members. Invite the "
    "Instructor with the role "
    "Reporter (read-only). A public project needs nothing."
)
READABLE = (
    "Readable: the course GitHub App can read `{repository}`. "
    "Only access was checked, never the contents."
)
YOUR_EVIDENCE_PROJECT = "Your Evidence Project: the Reading Day reads it in any case."
NOT_READABLE = "Not readable yet: grant read-only access."
NOT_CHECKED = (
    "Not readable yet, as far as the workspace can tell: it could not check access "
    "just now. "
    "Grant read-only access, then press Check again."
)


def github_how(app_slug: str, name: str) -> str:
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


class NotAProject(ValueError):
    """A URL that is not a GitHub or GitLab project."""


@dataclass(frozen=True)
class Project:
    host: Host
    repository: (
        str  # "owner/name"; on GitLab, the project's full path ("group/subgroup/name")
    )

    @property
    def url(self) -> str:
        return f"https://{self.host}.com/{self.repository}"

    @property
    def name(self) -> str:
        return self.repository.rsplit("/", 1)[-1]


_SEGMENT = re.compile(r"^[\w.-]+$")


def parse_project(url: str) -> Project:
    """The project a URL points into: its repository page, or any page inside it."""
    m = re.match(r"^https://(?:www\.)?(github|gitlab)\.com/([^?#]+)", url.strip())
    if not m:
        raise NotAProject(
            "Give the address of a repository on GitHub or GitLab, starting with https://"
        )
    host, path = m.group(1), m.group(2)
    parts = [p for p in path.split("/") if p]
    if host == GITHUB:
        parts = parts[:2]
    elif "-" in parts:  # GitLab: /group/project/-/tree/main
        parts = parts[: parts.index("-")]
    if len(parts) < 2 or not all(_SEGMENT.match(p) for p in parts):
        raise NotAProject(
            "Give the address of a repository: https://github.com/<owner>/<repository>"
        )
    parts[-1] = parts[-1].removesuffix(".git")
    return Project(host, "/".join(parts))  # type: ignore[arg-type]


class AccessCheck(Protocol):
    def can_read(self, repository: str) -> bool | None:
        """Whether the course GitHub App can read a GitHub repository; None when it
        could not check."""


def access(
    project: Project, evidence_project: str, check: AccessCheck, app_slug: str
) -> Access:
    """What the Student reads about a declared project's access."""
    if project.host == GITLAB:
        return Access(status=GITLAB_ACCESS, message=GITLAB_MESSAGE, how=GITLAB_HOW)
    if project.repository.lower() == evidence_project.lower():
        return Access(status=READABLE_ACCESS, message=YOUR_EVIDENCE_PROJECT, how=None)
    readable = check.can_read(project.repository)
    if readable:
        return Access(
            status=READABLE_ACCESS,
            message=READABLE.format(repository=project.repository),
            how=None,
        )
    return Access(
        status=NOT_READABLE_ACCESS,
        message=NOT_READABLE if readable is False else NOT_CHECKED,
        how=github_how(app_slug, project.name),
    )


class AppAccessCheck:
    """Through the Student Connector App: installed on the repository, or the repository
    public.

    `GET /repos/{repo}/installation` with the App's JWT answers 200 when the App is
    installed with access to that repository; else a public repository is still
    readable. Answers are kept a minute.
    """

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
        self._seen: dict[str, tuple[float, bool | None]] = {}
        self._lock = threading.Lock()

    def can_read(self, repository: str) -> bool | None:
        with self._lock:
            seen = self._seen.get(repository.lower())
        if seen and self._clock() - seen[0] < self.TTL:
            return seen[1]
        answer = self._ask(repository)
        with self._lock:
            self._seen[repository.lower()] = (self._clock(), answer)
        return answer

    def _ask(self, repository: str) -> bool | None:
        if not (self._app_id and self._key):
            return None
        try:
            app_jwt = InstallationAuth(self._app_id, self._key, "").app_jwt()
            installed = self._client.get(
                f"/repos/{repository}/installation",
                headers={"Authorization": f"Bearer {app_jwt}"},
            )
            if installed.status_code == 200:
                return True
            if installed.status_code != 404:
                return None
            public = self._client.get(f"/repos/{repository}")
            if public.status_code == 200:
                return not public.json().get("private", True)
            return False if public.status_code == 404 else None
        except (httpx.HTTPError, ValueError):
            return None


class FakeAccessCheck:
    """For tests and local runs: `readable` repositories are readable, others not.

    With no set given, every repository is readable unless its name contains "private".
    """

    def __init__(self, readable: set[str] | Callable[[str], bool | None] | None = None):
        if readable is None:
            self.rule: Callable[[str], bool | None] = lambda repo: (
                "private" not in repo.lower()
            )
        elif callable(readable):
            self.rule = readable
        else:
            known = {r.lower() for r in readable}
            self.rule = lambda repo: repo.lower() in known
        self.checked: list[str] = []

    def can_read(self, repository: str) -> bool | None:
        self.checked.append(repository)
        return self.rule(repository)
