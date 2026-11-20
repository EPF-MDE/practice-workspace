"""The Store: every send a Student makes, kept with every version.

Its interface speaks the domain, never GitHub: *read a Student's record*,
*save an answer*, *save a drawing*, *save the Self-assessment*, *save the
Practice Plan*, *save a declaration*, *save a question*, *save a fork
snapshot*. Each `save_*` is one send: it stores a new dated entry and never
rewrites an earlier one, so a Student's record is the history of their sends,
and their current state is the latest entry of each kind.

Two implementations stand behind `Store`:

- `InMemoryStore` (here): tests and local runs.
- `GitHubStore` (`github.py`): one `rehearsal` issue per Student, one comment
  per send; a drawing's PNG and snapshot on `workspace-data` besides.

The Store checks no cut-off and no content: callers decide what may be sent
and when (the cut-off dates are the app's rules, not storage's).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.roster import Student
from app.store._model import (
    KINDS,
    MAX_SEND_CHARS,
    DrawingFiles,
    Entry,
    Kind,
    Record,
    SendTooLarge,
    Store,
    StoreUnavailable,
    check_size,
    drawing_paths,
    drawing_payload,
    snapshot_file,
)
from app.store.github import GitHubStore

__all__ = [
    "KINDS",
    "MAX_SEND_CHARS",
    "DrawingFiles",
    "Entry",
    "GitHubStore",
    "InMemoryStore",
    "Kind",
    "Record",
    "SendTooLarge",
    "Store",
    "StoreUnavailable",
    "drawing_paths",
]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class InMemoryStore:
    """The Store in memory: tests and local runs. Lost when the process stops.

    `writes` counts the sends it took, for the write-budget test: every
    `save_*` is one send.
    """

    clock: Callable[[], datetime] = _now
    writes: int = 0
    _entries: dict[int, list[Entry]] = field(default_factory=dict)
    _drawings: dict[tuple[int, str, str], DrawingFiles] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def open_record(self, student: Student) -> None:
        pass  # nothing to open: a record exists from its first send

    def record(self, student: Student) -> Record:
        with self._lock:
            return Record(student, tuple(self._entries.get(student.github_id, ())))

    def _append(
        self,
        student: Student,
        kind: Kind,
        competency: str,
        key: str | None,
        payload: dict[str, Any],
    ) -> Entry:
        check_size(payload)
        with self._lock:
            entries = self._entries.setdefault(student.github_id, [])
            version = 1 + sum(
                1
                for e in entries
                if (e.kind, e.competency, e.key) == (kind, competency, key)
            )
            entry = Entry(kind, competency, key, payload, version, self.clock())
            entries.append(entry)
            self.writes += 1
            return entry

    def save_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry:
        return self._append(
            student, Kind.ANSWER, competency, step, {"fields": dict(fields)}
        )

    def save_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry:
        payload = drawing_payload(
            student, competency, drawing, png, snapshot_file(snapshot)
        )
        check_size(payload)
        with self._lock:
            self._drawings[(student.github_id, competency, drawing)] = DrawingFiles(
                png, snapshot
            )
        return self._append(student, Kind.DRAWING, competency, drawing, payload)

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None:
        with self._lock:
            return self._drawings.get((student.github_id, competency, drawing))

    def save_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry:
        return self._append(
            student, Kind.CHECK_POINTS, competency, drawing, {"missed": list(missed)}
        )

    def save_self_assessment(
        self, student: Student, competency: str, levels: dict[str, Any]
    ) -> Entry:
        return self._append(
            student, Kind.SELF_ASSESSMENT, competency, None, dict(levels)
        )

    def save_practice_plan(
        self, student: Student, competency: str, plan: dict[str, Any]
    ) -> Entry:
        return self._append(student, Kind.PRACTICE_PLAN, competency, None, dict(plan))

    def save_declaration(
        self, student: Student, competency: str, declaration: dict[str, Any]
    ) -> Entry:
        return self._append(
            student, Kind.DECLARATION, competency, None, dict(declaration)
        )

    def save_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry:
        return self._append(student, Kind.QUESTION, competency, step, {"text": text})

    def save_fork_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry:
        return self._append(
            student, Kind.FORK_SNAPSHOT, competency, None, dict(snapshot)
        )
