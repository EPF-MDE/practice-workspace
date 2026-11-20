"""The roster: who may sign in, and their Group, Project and Evidence Project.

`roster.csv` on the `workspace-data` branch, one row per Student:
`github_login,github_id,name,group,project,evidence_project`. A Student is found by
the numeric `github_id`, never by login: a renamed account still gets in, and
whoever takes over a freed login does not.
"""

from __future__ import annotations

import csv
import io
import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Group:
    """One of the two Groups, each with its own Project: the one place their names are
    spelt."""

    name: str  # as the roster spells it, in `group` and `project`
    directive: (
        str  # the content's block holding what only this Group receives: `::: oceens`
    )
    # its Project's repository, the one each Student's Evidence Project comes from
    upstream: str


GROUPS: dict[str, Group] = {
    g.name: g
    for g in (
        Group("OcéENS", "oceens", "EPF-MDE/OceENS"),
        Group("MATHutrice", "mathutrice", "EPF-MDE/MATHutrice"),
    )
}


@dataclass(frozen=True)
class Student:
    github_id: int
    github_login: str
    name: str
    group: str  # "OcéENS" or "MATHutrice"
    project: str  # the Group's Project, same values as `group`
    evidence_project: str  # "owner/repo"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Roster:
    """The Students on the Course's list, by numeric GitHub id."""

    def __init__(self, students: list[Student]):
        self._by_id = {student.github_id: student for student in students}

    def find(self, github_id: int) -> Student | None:
        return self._by_id.get(github_id)

    def __iter__(self) -> Iterator[Student]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


class RosterError(ValueError):
    """A roster the app refuses to read."""


COLUMNS = (
    "github_login",
    "github_id",
    "name",
    "group",
    "project",
    "evidence_project",
)


def parse_roster(text: str) -> Roster:
    """Read `roster.csv`'s text (CRLF or LF, an optional BOM)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = set(COLUMNS) - set(reader.fieldnames or ())
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
        for column in ("group", "project"):
            if row[column].strip() not in GROUPS:
                raise RosterError(
                    f"roster.csv line {line}: {column} {row[column].strip()!r} is not "
                    f"one of {sorted(GROUPS)}"
                )
        students.append(
            Student(
                github_id=github_id,
                github_login=row["github_login"].strip(),
                name=row["name"].strip(),
                group=row["group"].strip(),
                project=row["project"].strip(),
                evidence_project=row["evidence_project"].strip(),
            )
        )
    return Roster(students)


class RosterSource(Protocol):
    """Where the current roster comes from."""

    def current(self) -> Roster: ...


class StaticRoster:
    """A roster held in memory: tests, and a local roster file."""

    def __init__(self, roster: Roster):
        self._roster = roster

    def current(self) -> Roster:
        return self._roster

    def replace(self, roster: Roster) -> None:
        self._roster = roster

    @classmethod
    def from_file(cls, path: str | Path) -> StaticRoster:
        return cls(parse_roster(Path(path).read_text(encoding="utf-8")))


class RefreshingRoster:
    """A roster re-read at most every `max_age` seconds.

    `read` returns roster.csv's text (in production, from the data branch). So
    the Instructor adds a Student by pushing to `workspace-data`, without a
    deploy. If a re-read fails, the last roster read is kept.
    """

    def __init__(
        self,
        read: Callable[[], str],
        max_age: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._read = read
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
                    self._roster = parse_roster(self._read())
                    self._read_at = now
                except Exception:
                    if self._roster is None:
                        raise
                    logger.exception(
                        "roster.csv could not be re-read; keeping the last roster"
                    )
                    self._read_at = now
            return self._roster
