"""The GitHub seam: read-only GET requests on GitHub's REST API.

The fork reading only ever reads. Its adapters: `HttpGitHub` (production, with a token
provider) and `RecordedGitHub` (tests, replaying recorded responses).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

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


class HttpGitHub:
    """GitHub over HTTP. `token` returns a token for each request (refreshed by its
    provider)."""

    def __init__(self, token: Callable[[], str], client: httpx.Client | None = None):
        self._token = token
        self._client = client or httpx.Client(base_url=API, timeout=30)

    def get(self, path: str) -> Response:
        r = self._client.get(
            "/" + path.lstrip("/"),
            headers={**HEADERS, "Authorization": f"Bearer {self._token()}"},
        )
        if r.status_code >= 500:
            raise GitHubError(f"GET {path}: {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            body = None
        return Response(r.status_code, body, next_page_path(r.headers.get("link")))


def static_token(token: str) -> Callable[[], str]:
    return lambda: token


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
