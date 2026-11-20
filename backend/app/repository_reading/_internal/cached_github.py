from __future__ import annotations

import base64
import time
from typing import Any
from urllib.parse import quote

from ..github import GitHub, GitHubError, Response
from ..reading import StudentToRead
from .rules import COURSE_PREFIX, UPSTREAM_TTL


class _CachedGitHub:
    def __init__(self, github: GitHub):
        self._github = github
        self._comparisons: dict[tuple[str, str, str], dict[str, Any] | None] = {}
        self._upstream: dict[str, tuple[float, dict[str, str]]] = {}

    def get(self, path: str) -> Response:
        return self._github.get(path)

    def get_all(self, path: str) -> list[Any]:
        items: list[Any] = []
        next_path: str | None = path
        while next_path:
            r = self._github.get(next_path)
            if r.status != 200:
                raise GitHubError(f"GET {next_path}: {r.status}")
            items.extend(r.body)
            next_path = r.next_page
        return items

    def list_refs(
        self, student: StudentToRead
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return (
            self.get_all(f"repos/{student.evidence_project}/branches?per_page=100"),
            self.get_all(
                f"repos/{student.evidence_project}/pulls?state=all&per_page=100"
            ),
        )

    def upstream_branches(self, upstream: str) -> dict[str, str]:
        cached = self._upstream.get(upstream)
        if cached and time.monotonic() - cached[0] < UPSTREAM_TTL:
            return cached[1]
        branches = self.get_all(f"repos/{upstream}/branches?per_page=100")
        course = {
            b["name"]: b["commit"]["sha"]
            for b in branches
            if b["name"].startswith(COURSE_PREFIX)
        }
        self._upstream[upstream] = (time.monotonic(), course)
        return course

    def compare(self, repo: str, base: str, head: str) -> dict[str, Any] | None:
        key = (repo, base, head)
        if key not in self._comparisons:
            r = self._github.get(f"repos/{repo}/compare/{base}...{head}?per_page=100")
            self._comparisons[key] = r.body if r.status == 200 else None
        return self._comparisons[key]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        r = self._github.get(f"repos/{repo}/contents/{quote(path)}?ref={sha}")
        if r.status != 200 or not isinstance(r.body, dict) or "content" not in r.body:
            return None
        return base64.b64decode(r.body["content"]).decode("utf-8", "replace")
