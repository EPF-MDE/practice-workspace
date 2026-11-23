from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast

from app.roster import Repository, Student
from app.store._internal.payloads import (
    AnswerPayload,
    CheckPointsPayload,
    DeclarationPayload,
    DrawingPayload,
    EvidencePanelSnapshotPayload,
    EvidencePlanPayload,
    Host,
    Kind,
    Payload,
    QuestionPayload,
    SelfAssessmentPayload,
    WithdrawalPayload,
)

EVERY_COMPETENCY = None


@dataclass(frozen=True)
class Entry[P: Payload]:
    competency: str | None
    step_or_drawing: str | None
    payload: P
    version: int
    at: datetime

    @property
    def kind(self) -> Kind:
        return self.payload.KIND


@dataclass(frozen=True)
class StoredDeclaration:
    url: str
    what_to_read: str
    repository: Repository
    host: Host
    access_when_declared: str
    at: datetime

    @classmethod
    def from_payload(
        cls, payload: DeclarationPayload, at: datetime
    ) -> StoredDeclaration:
        return cls(
            url=payload.url,
            what_to_read=payload.what_to_read,
            repository=payload.repository,
            host=payload.host,
            access_when_declared=payload.access_when_declared,
            at=at,
        )


@dataclass(frozen=True)
class DrawingFiles:
    png: bytes
    snapshot: dict[str, Any]


DRAWINGS_FOLDER = "drawings"


def drawing_paths(student: Student, competency: str, drawing: str) -> tuple[str, str]:
    base = f"{DRAWINGS_FOLDER}/{student.github_login}/{competency}/{drawing}"
    return f"{base}.png", f"{base}.snapshot.json"


def snapshot_file(snapshot: dict[str, Any]) -> bytes:
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def drawing_payload(
    student: Student,
    competency: str,
    drawing: str,
    png: bytes,
    snapshot: bytes,
    commit: str | None = None,
) -> DrawingPayload:
    png_path, snapshot_path = drawing_paths(student, competency, drawing)
    return DrawingPayload(
        png=png_path,
        png_bytes=len(png),
        snapshot=snapshot_path,
        snapshot_bytes=len(snapshot),
        commit=commit,
    )


@dataclass(frozen=True)
class Record:
    student: Student
    entries: tuple[Entry[Payload], ...] = ()

    def history[P: Payload](
        self,
        payload: type[P],
        competency: str | None,
        step_or_drawing: str | None = None,
    ) -> list[Entry[P]]:
        return [
            e
            for e in self.all(payload, competency)
            if (e.competency, e.step_or_drawing) == (competency, step_or_drawing)
        ]

    def latest[P: Payload](
        self,
        payload: type[P],
        competency: str | None,
        step_or_drawing: str | None = None,
    ) -> Entry[P] | None:
        versions = self.history(payload, competency, step_or_drawing)
        return versions[-1] if versions else None

    def all[P: Payload](
        self, payload: type[P], competency: str | None = None
    ) -> list[Entry[P]]:
        return [
            cast(Entry[P], e)
            for e in self.entries
            if isinstance(e.payload, payload) and competency in (None, e.competency)
        ]

    def declaration(self) -> StoredDeclaration | None:
        found: StoredDeclaration | None = None
        for entry in self.entries:
            match entry.payload:
                case DeclarationPayload():
                    found = StoredDeclaration.from_payload(entry.payload, entry.at)
                case WithdrawalPayload():
                    found = None
                case EvidencePlanPayload(declaration=DeclarationPayload() as declared):
                    found = StoredDeclaration.from_payload(declared, entry.at)
        return found

    def missed_check_points(self, competency: str, drawing: str) -> list[str] | None:
        missed = None
        for entry in self.entries:
            if entry.competency != competency:
                continue
            match entry.payload:
                case CheckPointsPayload() if entry.step_or_drawing == drawing:
                    missed = entry.payload.missed
                case SelfAssessmentPayload() if (
                    drawing in entry.payload.missed_check_points
                ):
                    missed = entry.payload.missed_check_points[drawing]
        return missed


GITHUB_COMMENT_LIMIT = 65_536
LINE_CHARS = 1_000
MAX_SEND_CHARS = 63_000


def payload_json(payload: Payload) -> str:
    return json.dumps(payload.stored(), ensure_ascii=False, separators=(", ", ": "))


def check_size(payload: Payload) -> None:
    if len(payload_json(payload)) > MAX_SEND_CHARS:
        raise SendTooLarge(
            f"a send holds at most {MAX_SEND_CHARS:,} characters of JSON"
        )


class SendTooLarge(ValueError):
    pass


class StoreUnavailable(RuntimeError):
    pass


class Store(Protocol):
    def open_record(self, student: Student) -> None: ...

    def record(self, student: Student) -> Record: ...

    def records(self, students: list[Student]) -> list[Record]: ...

    def send_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry[AnswerPayload]: ...

    def send_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry[DrawingPayload]: ...

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None: ...

    def send_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry[CheckPointsPayload]: ...

    def send_self_assessment(
        self, student: Student, competency: str, assessment: SelfAssessmentPayload
    ) -> Entry[SelfAssessmentPayload]: ...

    def send_evidence_plan(
        self, student: Student, competency: str, plan: EvidencePlanPayload
    ) -> Entry[EvidencePlanPayload]: ...

    def send_declaration(
        self, student: Student, declaration: DeclarationPayload
    ) -> Entry[DeclarationPayload]: ...

    def withdraw_declaration(self, student: Student) -> Entry[WithdrawalPayload]: ...

    def send_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry[QuestionPayload]: ...

    def send_evidence_panel_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry[EvidencePanelSnapshotPayload]: ...
