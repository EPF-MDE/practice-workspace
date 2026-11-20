"""Reading a Student's repository: the rules of #451 points 2 to 8, as amended by #460.

- Every branch and the head of every pull request (closed, or with its branch deleted)
  is read.
- The Student's work is what a ref changes beyond every upstream `course-2026*` branch,
  whoever authored it: each ref is compared with each upstream `course-2026*` branch,
  and a file counts only if it differs in every comparison (its smallest difference is
  kept). Code brought in by a Fallback Branch or a Worked Example is therefore credited
  to that branch, never to the Student.
- Comparisons are cached by the pair of SHAs. A refresh lists the repository's refs (2
  requests) and recomputes only the refs whose tip changed.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ._internal.one_reading import _Reading
from ._internal.rules import (
    COURSE_PREFIX,
    UPSTREAM_TTL,
    _ref_shas,
)
from .github import GitHub, GitHubError
from .reading import (
    RepositoryReading,
    StudentToRead,
)
from .storage import ReadingStore


class RepositoryReader:
    """The Repository reading. One instance serves every Student: its caches are
    shared."""

    def __init__(
        self,
        github: GitHub,
        readings: ReadingStore,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.github = github
        self.readings = readings
        self.now = now
        self._comparisons: dict[
            tuple[str, str, str], dict[str, Any] | None
        ] = {}  # (repo, base sha, head sha)
        self._upstream: dict[str, tuple[float, dict[str, str]]] = {}

    # --- The interface
    # ---------------------------------------------------------------------

    def read(self, student: StudentToRead) -> RepositoryReading:
        """The stored reading (the batch's, or the last refresh's); a repository never
        read is read now."""
        stored = self._stored(student)
        if stored is not None:
            return stored
        return self.read_now(student)

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        """Lists the repository's refs; recomputes only if a ref changed (else 2
        requests)."""
        stored = self._stored(student)
        if stored is None:
            return self.read_now(student)
        branches, pulls = _ref_shas(*self._list_refs(student))
        if branches == stored.refs.get("branches") and pulls == stored.refs.get(
            "pulls"
        ):
            fresh = replace(stored, checked_at=self.now())
            self.readings.save(student.login, fresh, changed=False)
            return fresh
        return self.read_now(student, previous=stored)

    def _stored(self, student: StudentToRead) -> RepositoryReading | None:
        """The Student's stored reading, unless it reads another Evidence Project than
        the one asked for (the Student changed it since)."""
        stored = self.readings.load(student.login)
        if stored is None or not stored.reads(student):
            return None
        return stored

    def read_now(
        self, student: StudentToRead, previous: RepositoryReading | None = None
    ) -> RepositoryReading:
        """A full reading, reusing what `previous` computed for refs that did not
        change."""
        reading = _Reading(self, student, previous).run()
        self.readings.save(student.login, reading, changed=True)
        return reading

    # --- GitHub, cached
    # --------------------------------------------------------------------

    def get_all(self, path: str) -> list[Any]:
        items: list[Any] = []
        next_path: str | None = path
        while next_path:
            r = self.github.get(next_path)
            if r.status != 200:
                raise GitHubError(f"GET {next_path}: {r.status}")
            items.extend(r.body)
            next_path = r.next_page
        return items

    def _list_refs(
        self, student: StudentToRead
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Every branch, and every pull request with its head (`refs/pull/<n>/head`): 2
        requests."""
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
        """`base...head` on `repo`, by SHA; None if GitHub cannot compare them."""
        key = (repo, base, head)
        if key not in self._comparisons:
            r = self.github.get(f"repos/{repo}/compare/{base}...{head}?per_page=100")
            self._comparisons[key] = r.body if r.status == 200 else None
        return self._comparisons[key]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        r = self.github.get(f"repos/{repo}/contents/{quote(path)}?ref={sha}")
        if r.status != 200 or not isinstance(r.body, dict) or "content" not in r.body:
            return None
        return base64.b64decode(r.body["content"]).decode("utf-8", "replace")
