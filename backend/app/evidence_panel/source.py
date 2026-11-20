"""Where the panel gets a reading of the Evidence Project from, and which one it reads.

In production, the Repository reading itself
(`app.repository_reading.RepositoryReader`), built lazily so that an app whose Student
Connector has no installation yet still starts. Locally and in tests,
`OfflineRepositoryReading`: readings set by hand or read from a folder, never GitHub.
"""

from __future__ import annotations

import logging
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

from .panel import (
    Declaration,
    EvidencePanel,
    build_panel,
    not_read_text,
    unavailable_panel,
)

logger = logging.getLogger("app.evidence_panel")


class RepositoryReadingSource(Protocol):
    def read(self, student: StudentToRead) -> RepositoryReading: ...

    def refresh(self, student: StudentToRead) -> RepositoryReading: ...


def read_panel(
    competency: str,
    source: RepositoryReadingSource,
    student: StudentToRead,
    declaration: Declaration | None,
    refresh: bool = False,
) -> EvidencePanel:
    """The panel of one Competency, read from the Evidence Project the Reading Day
    reads: the one declared, else the roster's. A declared project the App cannot read
    is said as such, and never read as a zero."""
    if declaration is not None and not declaration.is_roster_evidence_project:
        if declaration.access.status != "readable":
            return unavailable_panel(
                competency,
                declaration.repository,
                declaration,
                not_read_text(declaration),
            )
        student = replace(student, evidence_project=declaration.repository)
    try:
        reading = source.refresh(student) if refresh else source.read(student)
    except Exception:  # the panel says so; the page and the closing step go on
        logger.exception("The Evidence Project of %s could not be read", student.login)
        return unavailable_panel(competency, student.evidence_project, declaration)
    return build_panel(competency, reading, declaration)


class OfflineRepositoryReading:
    """A fake Repository reading. `seed` (e.g. a folder of readings) is only read;
    changes stay in memory.

    A repository with no reading reads as a repository with its default branch only:
    empty. Readings are kept per Student and Evidence Project.
    """

    def __init__(
        self,
        seed: ReadingStore | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._seed = seed
        self._now = now
        self._readings: dict[tuple[str, str], RepositoryReading] = {}
        self.refreshes = 0

    def put(self, reading: RepositoryReading) -> None:
        self._readings[_key(reading.student)] = reading

    def read(self, student: StudentToRead) -> RepositoryReading:
        seeded = self._seed.load(student.login) if self._seed else None
        if seeded is not None and not seeded.reads(student):
            seeded = None
        found = self._readings.get(_key(student)) or seeded or self._empty(student)
        self._readings[_key(student)] = found
        return found

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        self.refreshes += 1
        fresh = replace(self.read(student), checked_at=self._now())
        self._readings[_key(student)] = fresh
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


def _key(student: StudentToRead) -> tuple[str, str]:
    return student.login, student.evidence_project.lower()


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
