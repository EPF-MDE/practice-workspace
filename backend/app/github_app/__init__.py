from __future__ import annotations

import base64
import threading
import time
from collections.abc import Callable, Generator

import httpx
import jwt

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


_BRANCH_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_BRANCH_LOCKS_GUARD = threading.Lock()


def data_branch_lock(repository: str, branch: str) -> threading.Lock:
    with _BRANCH_LOCKS_GUARD:
        return _BRANCH_LOCKS.setdefault((repository, branch), threading.Lock())


def private_key_from_base64(value: str) -> str:
    return base64.b64decode(value).decode("ascii")


class InstallationAuth(httpx.Auth):
    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        installation_id: str,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._app_id = app_id
        self._key = private_key_pem
        self._installation_id = installation_id
        self._clock = clock
        self._lock = threading.Lock()
        self._token = ""
        self._expires_at = 0.0

    def app_jwt(self) -> str:
        now = int(self._clock())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self._app_id}
        return jwt.encode(payload, self._key, algorithm="RS256")

    def token(self) -> str:
        with self._lock:
            if self._clock() > self._expires_at - 300:
                response = httpx.post(
                    f"{API}/app/installations/{self._installation_id}/access_tokens",
                    headers={**HEADERS, "Authorization": f"Bearer {self.app_jwt()}"},
                    timeout=20,
                )
                response.raise_for_status()
                self._token = response.json()["token"]
                self._expires_at = self._clock() + 3600
            return self._token

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        yield request


def installation_client(
    app_id: str, private_key_base64: str, installation_id: str
) -> httpx.Client:
    auth = InstallationAuth(
        app_id, private_key_from_base64(private_key_base64), installation_id
    )
    return httpx.Client(base_url=API, headers=HEADERS, auth=auth, timeout=20)


def read_file(client: httpx.Client, repository: str, branch: str, path: str) -> str:
    response = client.get(
        f"/repos/{repository}/contents/{path}",
        params={"ref": branch},
        headers={"Accept": "application/vnd.github.raw+json"},
    )
    response.raise_for_status()
    return response.content.decode("utf-8")
