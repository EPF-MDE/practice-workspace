"""The GitHub seam: read-only GET requests on GitHub's REST API.

The Repository reading only ever reads. Its adapters: `HttpGitHub` (production, with a
token provider) and `RecordedGitHub` (tests, replaying recorded responses).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from app.github_app import API, HEADERS, InstallationAuth, private_key_from_base64


@dataclass(frozen=True)
class Response:
    status: int
    body: Any
    next_page: str | None = None  # the path of the next page, from the Link header


class GitHub(Protocol):
    """One read-only request. `path` is relative to the API root, with its query."""

    def get(self, path: str) -> Response: ...


class GitHubError(RuntimeError):
    pass


_NEXT = re.compile(r'<https://api\.github\.com(/[^>]+)>;\s*rel="next"')


def next_page_path(link_header: str | None) -> str | None:
    if not link_header:
        return None
    m = _NEXT.search(link_header)
    return m.group(1).lstrip("/") if m else None


# How long a repository the App is not installed on is read with the default token,
# before asking again.
INSTALLED_TTL = 15 * 60

# A token for a repository ("owner/name"), refreshed by its provider.
TokenFor = Callable[[str], str]


class HttpGitHub:
    """GitHub over HTTP. `token` gives a token for the repository each request reads."""

    def __init__(self, token: TokenFor, client: httpx.Client | None = None):
        self._token = token
        self._client = client or httpx.Client(base_url=API, timeout=30)

    def get(self, path: str) -> Response:
        token = self._token(repository_of(path))
        r = self._client.get(
            "/" + path.lstrip("/"),
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
        )
        if r.status_code >= 500:
            raise GitHubError(f"GET {path}: {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            body = None
        return Response(r.status_code, body, next_page_path(r.headers.get("link")))


def repository_of(path: str) -> str:
    """The repository ("owner/name") a request reads: every path the Repository reading
    asks is `repos/{owner}/{name}/...`."""
    return "/".join(path.lstrip("/").split("/")[1:3])


def static_token(token: str) -> TokenFor:
    return lambda repository: token


class _Installation(BaseModel):
    id: int


def repository_tokens(
    app_id: str,
    private_key_base64: str,
    installation_id: str = "",
    clock: Callable[[], float] = time.monotonic,
) -> TokenFor:
    """The Student Connector App's token for each repository: its installation on that
    repository, so that a private repository it was installed on can be read; else the
    `installation_id` one (or the first), which reads any public repository."""
    pem = private_key_from_base64(private_key_base64)

    def installed(repository: str) -> Callable[[], str] | None:
        app_jwt = InstallationAuth(app_id, pem, "").app_jwt()
        found = httpx.get(
            f"{API}/repos/{repository}/installation",
            headers={**HEADERS, "Authorization": f"Bearer {app_jwt}"},
            timeout=20,
        )
        if found.status_code != 200:
            return None
        installation = _Installation.model_validate(found.json())
        return InstallationAuth(app_id, pem, str(installation.id)).token

    return tokens_per_repository(
        installed,
        installation_token(app_id, private_key_base64, installation_id),
        clock,
    )


def tokens_per_repository(
    installed: Callable[[str], Callable[[], str] | None],
    default: Callable[[], str],
    clock: Callable[[], float] = time.monotonic,
) -> TokenFor:
    """The token of the installation `installed` finds on each repository, asked once;
    else `default`'s, until INSTALLED_TTL has passed and the repository is asked
    again."""
    # per repository: when it was asked, and its installation's token provider if any
    seen: dict[str, tuple[float, Callable[[], str] | None]] = {}

    def token(repository: str) -> str:
        key = repository.lower()
        if key not in seen or (
            seen[key][1] is None and clock() - seen[key][0] > INSTALLED_TTL
        ):
            seen[key] = (clock(), installed(repository))
        return (seen[key][1] or default)()

    return token


def installation_token(
    app_id: str, private_key_base64: str, installation_id: str = ""
) -> Callable[[], str]:
    """A token provider for one installation of a GitHub App (`app.github_app` renews
    it).

    With no `installation_id`, the App's first installation is used.
    """
    pem = private_key_from_base64(private_key_base64)
    if not installation_id:
        app_jwt = InstallationAuth(app_id, pem, "").app_jwt()
        found = httpx.get(
            f"{API}/app/installations",
            headers={**HEADERS, "Authorization": f"Bearer {app_jwt}"},
            timeout=20,
        )
        found.raise_for_status()
        if not found.json():
            raise GitHubError(
                "The GitHub App has no installation: install it (read-only) "
                "on an account first, or pass another token."
            )
        installation_id = str(found.json()[0]["id"])
    return InstallationAuth(app_id, pem, installation_id).token
