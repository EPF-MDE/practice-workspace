"""Where readings are kept: one JSON file per Student, `fork-readings/<login>.json` on
`workspace-data`.

`ReadingStore` is the seam. Adapters: `InMemoryReadings` (tests, local development),
`DirectoryReadings` (a local folder: the batch's dry run), and `WorkspaceDataReadings`
(the `workspace-data` branch, through a `WorkspaceData` writer).
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from app.github_app import data_branch_lock

if TYPE_CHECKING:
    from .reading import ForkReading

READINGS_DIR = "fork-readings"
BRANCH = "workspace-data"


def reading_path(login: str) -> str:
    return f"{READINGS_DIR}/{login}.json"


def encode(reading: ForkReading) -> bytes:
    return (
        json.dumps(reading.to_dict(), indent=1, ensure_ascii=False, sort_keys=True)
        + "\n"
    ).encode()


def decode(data: bytes) -> ForkReading:
    from .reading import ForkReading

    return ForkReading.from_dict(json.loads(data))


class ReadingStore(Protocol):
    def load(self, login: str) -> ForkReading | None: ...

    def save(self, login: str, reading: ForkReading, changed: bool = True) -> None:
        """`changed=False`: only the time of the check moved; nothing needs writing to
        GitHub."""


class InMemoryReadings:
    def __init__(self) -> None:
        self.readings: dict[str, ForkReading] = {}
        self.writes = 0

    def load(self, login: str) -> ForkReading | None:
        return self.readings.get(login)

    def save(self, login: str, reading: ForkReading, changed: bool = True) -> None:
        self.readings[login] = reading
        self.writes += changed


class DirectoryReadings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, login: str) -> ForkReading | None:
        p = self.root / reading_path(login)
        return decode(p.read_bytes()) if p.exists() else None

    def save(self, login: str, reading: ForkReading, changed: bool = True) -> None:
        p = self.root / reading_path(login)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encode(reading))


class WorkspaceData(Protocol):
    """The `workspace-data` branch of this repo."""

    def read(self, path: str) -> bytes | None: ...

    def write(self, files: dict[str, bytes], message: str) -> None:
        """Writes every file in one commit."""


class WorkspaceDataReadings:
    """Readings on `workspace-data`, kept in memory once read. A check with no change
    writes nothing."""

    def __init__(self, data: WorkspaceData) -> None:
        self.data = data
        self._memory: dict[str, ForkReading] = {}

    def load(self, login: str) -> ForkReading | None:
        if login not in self._memory:
            raw = self.data.read(reading_path(login))
            if raw is None:
                return None
            self._memory[login] = decode(raw)
        return self._memory[login]

    def save(self, login: str, reading: ForkReading, changed: bool = True) -> None:
        self._memory[login] = reading
        if changed:
            self.data.write(
                {reading_path(login): encode(reading)},
                f"data: read the fork of {login}",
            )


class GitHubWorkspaceData:
    """`workspace-data` through GitHub's Git Data API: many files, one commit.

    A write is 5 requests, whatever the number of files. Writes are serialised by the
    one in-process lock of that branch (`data_branch_lock`, which the Store's drawings
    take too) and retried when the branch moved meanwhile. `token` is a token with
    Contents write on the repo (the Store App's installation token).
    """

    def __init__(
        self,
        repo: str,
        token: Callable[[], str],
        client: httpx.Client | None = None,
        branch: str = BRANCH,
        retries: int = 3,
    ) -> None:
        self.repo, self.branch, self.retries = repo, branch, retries
        self._token = token
        self._client = client or httpx.Client(
            base_url="https://api.github.com", timeout=30
        )
        # Shared with the Store's drawing writes: one in-process lock per data branch.
        self._lock = data_branch_lock(repo, branch)

    def _req(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return self._client.request(
            method,
            f"/repos/{self.repo}/{path}",
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Accept": "application/vnd.github+json",
            },
            **kw,
        )

    def read(self, path: str) -> bytes | None:
        r = self._req("GET", f"contents/{path}", params={"ref": self.branch})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.json()
        if body.get("content"):
            return base64.b64decode(body["content"])
        blob = self._req("GET", f"git/blobs/{body['sha']}")  # files over 1 MB
        blob.raise_for_status()
        return base64.b64decode(blob.json()["content"])

    def write(self, files: dict[str, bytes], message: str) -> None:
        with self._lock:
            for attempt in range(self.retries):
                head = self._req("GET", f"git/ref/heads/{self.branch}")
                head.raise_for_status()
                parent = head.json()["object"]["sha"]
                commit = self._req("GET", f"git/commits/{parent}").json()
                # Readings are UTF-8 JSON, so they go inline in the tree: no request per
                # file.
                tree = [
                    {"path": p, "mode": "100644", "type": "blob", "content": d.decode()}
                    for p, d in files.items()
                ]
                new_tree = self._req(
                    "POST",
                    "git/trees",
                    json={"base_tree": commit["tree"]["sha"], "tree": tree},
                )
                new_tree.raise_for_status()
                new_commit = self._req(
                    "POST",
                    "git/commits",
                    json={
                        "message": message,
                        "tree": new_tree.json()["sha"],
                        "parents": [parent],
                    },
                )
                new_commit.raise_for_status()
                moved = self._req(
                    "PATCH",
                    f"git/refs/heads/{self.branch}",
                    json={"sha": new_commit.json()["sha"], "force": False},
                )
                if moved.status_code == 200:
                    return
                if (
                    moved.status_code != 422
                ):  # 422: not a fast-forward, the branch moved meanwhile
                    moved.raise_for_status()
                time.sleep(0.5 * (attempt + 1))
            raise RuntimeError(
                f"{self.branch} kept moving: {len(files)} files not written"
            )
