from __future__ import annotations

import csv
import io
import logging
import threading
import time
from collections.abc import Callable, Collection, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, NewType, Protocol

logger = logging.getLogger(__name__)


Repository = NewType("Repository", str)


@dataclass(frozen=True)
class Student:
    github_id: int
    github_login: str
    name: str
    group: str
    evidence_project: Repository | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Roster:
    def __init__(self, students: list[Student]):
        self._by_id = {student.github_id: student for student in students}

    def find(self, github_id: int) -> Student | None:
        return self._by_id.get(github_id)

    def __iter__(self) -> Iterator[Student]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


class RosterError(ValueError):
    pass


COLUMNS = ("github_login", "github_id", "name", "group")
EVIDENCE_PROJECT = "evidence_project"


def parse_roster(
    text: str, groups: Collection[str], names_evidence_projects: bool
) -> Roster:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    columns = COLUMNS + ((EVIDENCE_PROJECT,) if names_evidence_projects else ())
    missing = set(columns) - set(reader.fieldnames or ())
    if missing:
        raise RosterError(f"roster.csv lacks the columns {sorted(missing)}")
    students = []
    for line, row in enumerate(reader, start=2):
        try:
            github_id = int(row["github_id"].strip())
        except ValueError:
            raise RosterError(
                f"roster.csv line {line}: github_id is not a number"
            ) from None
        group = row["group"].strip()
        if group not in groups:
            raise RosterError(
                f"roster.csv line {line}: the Group {group!r} is not one of the "
                f"Course's {sorted(groups)}"
            )
        evidence_project = None
        if names_evidence_projects:
            evidence_project = Repository((row[EVIDENCE_PROJECT] or "").strip())
            if not evidence_project:
                raise RosterError(
                    f"roster.csv line {line}: no Evidence Project, and the Course "
                    "reads the one the Roster names when a Student declares none"
                )
        students.append(
            Student(
                github_id=github_id,
                github_login=row["github_login"].strip(),
                name=row["name"].strip(),
                group=group,
                evidence_project=evidence_project,
            )
        )
    return Roster(students)


class RosterSource(Protocol):
    def current(self) -> Roster: ...


class StaticRoster:
    def __init__(self, roster: Roster):
        self._roster = roster

    def current(self) -> Roster:
        return self._roster

    def replace(self, roster: Roster) -> None:
        self._roster = roster

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        groups: Collection[str],
        names_evidence_projects: bool,
    ) -> StaticRoster:
        return cls(
            parse_roster(
                Path(path).read_text(encoding="utf-8"),
                groups,
                names_evidence_projects,
            )
        )


class RefreshingRoster:
    def __init__(
        self,
        read: Callable[[], str],
        groups: Collection[str],
        names_evidence_projects: bool,
        max_age: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._read = read
        self._groups = groups
        self._names_evidence_projects = names_evidence_projects
        self._max_age = max_age
        self._clock = clock
        self._lock = threading.Lock()
        self._roster: Roster | None = None
        self._read_at = 0.0

    def current(self) -> Roster:
        with self._lock:
            now = self._clock()
            if self._roster is None or now - self._read_at >= self._max_age:
                try:
                    self._roster = parse_roster(
                        self._read(), self._groups, self._names_evidence_projects
                    )
                    self._read_at = now
                except Exception:
                    if self._roster is None:
                        raise
                    logger.exception(
                        "roster.csv could not be re-read; keeping the last roster"
                    )
                    self._read_at = now
            return self._roster
