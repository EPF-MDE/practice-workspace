"""Where the panel gets a reading of the fork from.

In production, the fork reading itself (`app.fork_reading.ForkReader`), built
lazily so that an app whose Student Connector has no installation yet still
starts. Locally and in tests, `OfflineForkReading`: readings set by hand or
read from a folder, never GitHub.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from app.fork_reading import CompetencyReading, ForkReading, ReadingStore, StudentFork
from app.fork_reading.reading import LOOKED_FOR, NOT_VISIBLE


class ForkSource(Protocol):
    def read(self, student: StudentFork) -> ForkReading: ...

    def refresh(self, student: StudentFork) -> ForkReading: ...


class OfflineForkReading:
    """A fake fork reading. `seed` (e.g. a folder of readings) is only read; changes
    stay in memory.

    A fork with no reading reads as a fork with its default branch only: empty.
    """

    def __init__(
        self,
        seed: ReadingStore | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._seed = seed
        self._now = now
        self._readings: dict[str, ForkReading] = {}
        self.refreshes = 0

    def put(self, reading: ForkReading) -> None:
        self._readings[reading.student.login] = reading

    def read(self, student: StudentFork) -> ForkReading:
        found = self._readings.get(student.login) or (
            self._seed.load(student.login) if self._seed else None
        )
        if found is None:
            found = self._empty(student)
        self._readings[student.login] = found
        return found

    def refresh(self, student: StudentFork) -> ForkReading:
        self.refreshes += 1
        fresh = replace(self.read(student), checked_at=self._now())
        self._readings[student.login] = fresh
        return fresh

    def _empty(self, student: StudentFork) -> ForkReading:
        now = self._now()
        return ForkReading(
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


class LazyForkSource:
    """Builds the real source on first use, so an app starts even when GitHub cannot be
    reached."""

    def __init__(self, build: Callable[[], ForkSource]):
        self._build = build
        self._source: ForkSource | None = None
        self._lock = threading.Lock()

    def _get(self) -> ForkSource:
        with self._lock:
            if self._source is None:
                self._source = self._build()
            return self._source

    def read(self, student: StudentFork) -> ForkReading:
        return self._get().read(student)

    def refresh(self, student: StudentFork) -> ForkReading:
        return self._get().refresh(student)
