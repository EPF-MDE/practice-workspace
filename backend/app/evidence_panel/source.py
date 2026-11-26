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
from app.roster import Repository, Student

from .panel import (
    READABLE_ACCESS,
    CoursePoints,
    Declaration,
    EvidencePanel,
    build_panel,
    not_read_text,
    unavailable_panel,
    undeclared_panel,
)

logger = logging.getLogger("app.evidence_panel")


class RepositoryReadingSource(Protocol):
    def read(self, student: StudentToRead) -> RepositoryReading: ...

    def refresh(self, student: StudentToRead) -> RepositoryReading: ...


def read_panel(
    competency: str,
    points: CoursePoints,
    source: RepositoryReadingSource,
    on_the_roster: Student,
    upstream: Repository | None,
    declaration: Declaration | None,
    refresh: bool = False,
) -> EvidencePanel:
    evidence_project = on_the_roster.evidence_project
    if declaration is not None and not declaration.declares_roster_evidence_project:
        if declaration.access.status != READABLE_ACCESS:
            return unavailable_panel(
                competency,
                declaration.repository,
                declaration,
                not_read_text(declaration),
            )
        evidence_project = declaration.repository
    if evidence_project is None:
        return undeclared_panel(competency)
    student = StudentToRead.for_student(on_the_roster, evidence_project, upstream)
    try:
        reading = source.refresh(student) if refresh else source.read(student)
    except Exception:
        logger.exception("The Evidence Project of %s could not be read", student.login)
        return unavailable_panel(competency, student.evidence_project, declaration)
    return build_panel(competency, points, reading, declaration)


class OfflineRepositoryReading:
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
        self._readings[reading.student.key] = reading

    def read(self, student: StudentToRead) -> RepositoryReading:
        seeded = self._seed.load(student.login) if self._seed else None
        if seeded is not None and not seeded.reads(student):
            seeded = None
        found = self._readings.get(student.key) or seeded or self._empty(student)
        self._readings[student.key] = found
        return found

    def refresh(self, student: StudentToRead) -> RepositoryReading:
        self.refreshes += 1
        fresh = replace(self.read(student), last_checked_at=self._now())
        self._readings[student.key] = fresh
        return fresh

    def _empty(self, student: StudentToRead) -> RepositoryReading:
        now = self._now()
        return RepositoryReading(
            student=student,
            default_branch="main",
            facts_computed_at=now,
            last_checked_at=now,
            branches_read=1,
            pull_requests_read=0,
            empty=True,
            competencies={
                c: CompetencyReading(c, [], list(LOOKED_FOR[c]), list(NOT_VISIBLE[c]))
                for c in LOOKED_FOR
            },
        )


class LazyRepositoryReadingSource:
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
