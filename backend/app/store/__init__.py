from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.roster import Student
from app.store._internal.model import (
    EVERY_COMPETENCY,
    MAX_SEND_CHARS,
    DrawingFiles,
    Entry,
    Record,
    SendTooLarge,
    Store,
    StoredDeclaration,
    StoreUnavailable,
    check_size,
    drawing_paths,
    drawing_payload,
    snapshot_file,
)
from app.store._internal.payloads import (
    GITHUB,
    GITLAB,
    AnswerPayload,
    CheckPointsPayload,
    DeclarationPayload,
    DrawingPayload,
    EvidencePanelSnapshotPayload,
    EvidencePlanPayload,
    Host,
    Kind,
    Payload,
    PointLevelPayload,
    QuestionPayload,
    SelfAssessmentPayload,
    WithdrawalPayload,
)
from app.store.github import GitHubStore

__all__ = [
    "EVERY_COMPETENCY",
    "GITHUB",
    "GITLAB",
    "MAX_SEND_CHARS",
    "AnswerPayload",
    "DeclarationPayload",
    "DrawingFiles",
    "DrawingPayload",
    "Entry",
    "EvidencePlanPayload",
    "GitHubStore",
    "Host",
    "InMemoryStore",
    "Kind",
    "Payload",
    "PointLevelPayload",
    "QuestionPayload",
    "Record",
    "SelfAssessmentPayload",
    "SendTooLarge",
    "Store",
    "StoredDeclaration",
    "StoreUnavailable",
    "WithdrawalPayload",
    "drawing_paths",
]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class InMemoryStore:
    clock: Callable[[], datetime] = _now
    writes: int = 0
    _entries: dict[int, list[Entry[Payload]]] = field(default_factory=dict)
    _drawings: dict[tuple[int, str, str], DrawingFiles] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def open_record(self, student: Student) -> None:
        pass

    def record(self, student: Student) -> Record:
        with self._lock:
            return Record(student, tuple(self._entries.get(student.github_id, ())))

    def records(self, students: list[Student]) -> list[Record]:
        return [self.record(student) for student in students]

    def _append[P: Payload](
        self,
        student: Student,
        competency: str | None,
        step_or_drawing: str | None,
        payload: P,
    ) -> Entry[P]:
        check_size(payload)
        with self._lock:
            entries = self._entries.setdefault(student.github_id, [])
            version = 1 + sum(
                1
                for e in entries
                if (e.kind, e.competency, e.step_or_drawing)
                == (payload.KIND, competency, step_or_drawing)
            )
            entry = Entry(competency, step_or_drawing, payload, version, self.clock())
            entries.append(entry)
            self.writes += 1
            return entry

    def send_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry[AnswerPayload]:
        return self._append(student, competency, step, AnswerPayload(fields=fields))

    def send_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry[DrawingPayload]:
        payload = drawing_payload(
            student, competency, drawing, png, snapshot_file(snapshot)
        )
        check_size(payload)
        with self._lock:
            self._drawings[(student.github_id, competency, drawing)] = DrawingFiles(
                png, snapshot
            )
        return self._append(student, competency, drawing, payload)

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None:
        with self._lock:
            return self._drawings.get((student.github_id, competency, drawing))

    def send_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry[CheckPointsPayload]:
        return self._append(
            student, competency, drawing, CheckPointsPayload(missed=missed)
        )

    def send_self_assessment(
        self, student: Student, competency: str, assessment: SelfAssessmentPayload
    ) -> Entry[SelfAssessmentPayload]:
        return self._append(student, competency, None, assessment)

    def send_evidence_plan(
        self, student: Student, competency: str, plan: EvidencePlanPayload
    ) -> Entry[EvidencePlanPayload]:
        return self._append(student, competency, None, plan)

    def send_declaration(
        self, student: Student, declaration: DeclarationPayload
    ) -> Entry[DeclarationPayload]:
        return self._append(student, EVERY_COMPETENCY, None, declaration)

    def withdraw_declaration(self, student: Student) -> Entry[WithdrawalPayload]:
        return self._append(student, EVERY_COMPETENCY, None, WithdrawalPayload())

    def send_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry[QuestionPayload]:
        return self._append(student, competency, step, QuestionPayload(text=text))

    def send_evidence_panel_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry[EvidencePanelSnapshotPayload]:
        return self._append(
            student,
            competency,
            None,
            EvidencePanelSnapshotPayload.model_validate(snapshot),
        )
