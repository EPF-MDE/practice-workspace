"""Where the panel gets a reading of the repository from.

In production, the Repository reading itself
(`app.repository_reading.RepositoryReader`), built lazily so that an app whose Student
Connector has no installation yet still starts. Locally and in tests,
`OfflineRepositoryReading`: readings set by hand or read from a folder, never GitHub.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from app.repository_reading import (
    CompetencyReading,
    ReadingStore,
    RepositoryReading,
    StudentToRead,
)
from app.repository_reading.reading import LOOKED_FOR, NOT_VISIBLE


class RepositoryReadingSource(Protocol):
    def read(self, student: StudentToRead) -> RepositoryReading: ...

    def refresh(self, student: StudentToRead) -> RepositoryReading: ...


class OfflineRepositoryReading:
    """A fake Repository reading. `seed` (e.g. a folder of readings) is only read;
    changes stay in memory.

    A repository with no reading reads as a repository with its default branch only:
    empty.
    """

    def __init__(
        self,
        seed: ReadingStore | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._seed = seed
        self._now = now
        self._readings: dict[str, RepositoryReading] = {}
        self.refreshes = 0

    def put(self, reading: RepositoryReading) -> None:
        self._readings[reading.student.login] = reading

    def read(self, student: StudentToRead) -> RepositoryReading:
        found = self._readings.get(student.login) or (
            self._seed.load(student.login) if self._seed else None
        )
        if found is None:
            found = self._empty(student)
        self._readings[student.login] = found
        return found

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        self.refreshes += 1
        fresh = replace(self.read(student), checked_at=self._now())
        self._readings[student.login] = fresh
        return fresh

    def _empty(self, student: StudentToRead) -> RepositoryReading:
        now = self._now()
        return RepositoryReading(
            student=student,
            default_branch="main",
            read_at=now,
            checked_at=now,
            branches_read=1,
            pull_requests_read=0,
            empty=True,
            competencies={
                c: CompetencyReading(c, [], list(LOOKED_FOR[c]), list(NOT_VISIBLE[c]))
                for c in LOOKED_FOR
            },
        )


class LazyRepositoryReadingSource:
    """Builds the real source on first use, so an app starts even when GitHub cannot be
    reached."""

    def __init__(self, build: Callable[[], RepositoryReadingSource]):
        self._build = build
        self._source: RepositoryReadingSource | None = None
        self._lock = threading.Lock()

    def _get(self) -> RepositoryReadingSource:
        with self._lock:
            if self._source is None:
                self._source = self._build()
            return self._source

    def read(self, student: StudentToRead) -> RepositoryReading:
        return self._get().read(student)

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        return self._get().refresh(student)
