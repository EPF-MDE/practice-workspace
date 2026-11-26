from __future__ import annotations

import base64
from collections.abc import Callable

import httpx

from app.github_app import data_branch_lock
from app.store._internal.github_api import GitHubApi
from app.store._internal.model import StoreUnavailable

DATA_RETRIES = 5


class DataBranch:
    def __init__(self, api: GitHubApi, branch: str, sleep: Callable[[float], None]):
        self._api = api
        self.branch = branch
        self._sleep = sleep
        self._data_branch_lock = data_branch_lock(api.repository, branch)

    def write(self, folder: str, files: dict[str, bytes], message: str) -> str:
        with self._data_branch_lock:
            commit = ""
            for path, data in files.items():
                commit = self._put_file(folder, path, data, message)
            return commit

    def read(self, path: str, ref: str) -> bytes:
        return self._api.call(
            "GET",
            f"/repos/{self._api.repository}/contents/{path}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.raw+json"},
        ).content

    def _put_file(self, folder: str, path: str, data: bytes, message: str) -> str:
        url = f"/repos/{self._api.repository}/contents/"
        for attempt in range(DATA_RETRIES):
            body = {
                "message": message,
                "content": base64.b64encode(data).decode(),
                "branch": self.branch,
            }
            current = self._file_sha(folder, path)
            if current:
                body["sha"] = current
            try:
                response = self._api.http.put(url + path, json=body)
            except httpx.HTTPError as error:
                raise StoreUnavailable(f"GitHub did not answer: {error}") from error
            if response.status_code == 409:
                self._sleep(0.5 * (attempt + 1))
                continue
            if response.is_error:
                raise StoreUnavailable(
                    f"GitHub answered {response.status_code} to PUT {path}"
                )
            sha: str = response.json()["commit"]["sha"]
            return sha
        raise StoreUnavailable(f"{self.branch} kept moving: {path} not written")

    def _file_sha(self, folder: str, path: str) -> str | None:
        try:
            response = self._api.http.get(
                f"/repos/{self._api.repository}/contents/{folder}",
                params={"ref": self.branch},
            )
        except httpx.HTTPError as error:
            raise StoreUnavailable(f"GitHub did not answer: {error}") from error
        if response.status_code == 404:
            return None
        if response.is_error:
            raise StoreUnavailable(
                f"GitHub answered {response.status_code} to GET {folder}"
            )
        return next(
            (item["sha"] for item in response.json() if item["path"] == path), None
        )
