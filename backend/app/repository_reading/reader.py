from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from ._internal.cached_github import _CachedGitHub
from ._internal.one_reading import _Reading
from ._internal.rules import _ref_shas
from .github import GitHub
from .reading import (
    RepositoryReading,
    StudentToRead,
)
from .storage import ReadingStore


class RepositoryReader:
    def __init__(
        self,
        github: GitHub,
        readings: ReadingStore,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._github = _CachedGitHub(github)
        self.readings = readings
        self.now = now

    def read(self, student: StudentToRead) -> RepositoryReading:
        stored = self._stored(student)
        if stored is not None:
            return stored
        return self.read_now(student)

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        stored = self._stored(student)
        if stored is None:
            return self.read_now(student)
        branches, pulls = _ref_shas(*self._github.list_refs(student))
        if branches == stored.refs.get("branches") and pulls == stored.refs.get(
            "pulls"
        ):
            fresh = replace(stored, last_checked_at=self.now())
            self.readings.save(student.login, fresh, changed=False)
            return fresh
        return self.read_now(student, previous=stored)

    def _stored(self, student: StudentToRead) -> RepositoryReading | None:
        stored = self.readings.load(student.login)
        if stored is None or not stored.reads(student):
            return None
        return stored

    def read_now(
        self, student: StudentToRead, previous: RepositoryReading | None = None
    ) -> RepositoryReading:
        reading = _Reading(self._github, self.now, student, previous).run()
        self.readings.save(student.login, reading, changed=True)
        return reading
