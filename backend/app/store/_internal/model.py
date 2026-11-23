from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from app.roster import Repository, Student


class Kind(StrEnum):
    ANSWER = "answer"
    DRAWING = "drawing"
    CHECK_POINTS = "check-points"
    SELF_ASSESSMENT = "self-assessment"
    EVIDENCE_PLAN = "evidence-plan"
    DECLARATION = "declaration"
    QUESTION = "question"
    EVIDENCE_PANEL_SNAPSHOT = "evidence-panel-snapshot"


KINDS: tuple[Kind, ...] = tuple(Kind)

EVERY_COMPETENCY = None


@dataclass(frozen=True)
class Entry:
    kind: Kind
    competency: str | None
    key: str | None
    payload: dict[str, Any]
    version: int
    at: datetime


Host = Literal["github", "gitlab"]
GITHUB: Host = "github"
GITLAB: Host = "gitlab"
_HOSTS: dict[str, Host] = {GITHUB: GITHUB, GITLAB: GITLAB}


@dataclass(frozen=True)
class StoredDeclaration:
    url: str
    note: str
    repository: Repository
    host: Host
    access: str
    at: datetime

    @classmethod
    def from_payload(cls, payload: dict[str, Any], at: datetime) -> StoredDeclaration:
        return cls(
            url=payload["url"],
            note=payload["note"],
            repository=Repository(payload["repository"]),
            host=_HOSTS[payload["host"]],
            access=payload["access"],
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
    student: Student, competency: str, drawing: str, png: bytes, snapshot: bytes
) -> dict[str, Any]:
    png_path, snapshot_path = drawing_paths(student, competency, drawing)
    return {
        "png": png_path,
        "png_bytes": len(png),
        "snapshot": snapshot_path,
        "snapshot_bytes": len(snapshot),
    }


@dataclass(frozen=True)
class Record:
    student: Student
    entries: tuple[Entry, ...] = ()

    def history(
        self, kind: Kind, competency: str | None, key: str | None = None
    ) -> list[Entry]:
        return [
            e
            for e in self.entries
            if (e.kind, e.competency, e.key) == (kind, competency, key)
        ]

    def latest(
        self, kind: Kind, competency: str | None, key: str | None = None
    ) -> Entry | None:
        versions = self.history(kind, competency, key)
        return versions[-1] if versions else None

    def all(self, kind: Kind, competency: str | None = None) -> list[Entry]:
        return [
            e
            for e in self.entries
            if e.kind == kind and competency in (None, e.competency)
        ]

    def declaration(self) -> StoredDeclaration | None:
        found: tuple[dict[str, Any], datetime] | None = None
        for entry in self.entries:
            if entry.kind == Kind.DECLARATION:
                found = (entry.payload, entry.at) if entry.payload else None
            elif entry.kind == Kind.EVIDENCE_PLAN and "declaration" in entry.payload:
                found = (entry.payload["declaration"], entry.at)
        return None if found is None else StoredDeclaration.from_payload(*found)

    def missed_check_points(self, competency: str, drawing: str) -> list[str] | None:
        missed = None
        for entry in self.entries:
            if entry.competency != competency:
                continue
            if entry.kind == Kind.CHECK_POINTS and entry.key == drawing:
                missed = entry.payload["missed"]
            elif entry.kind == Kind.SELF_ASSESSMENT and drawing in entry.payload.get(
                "missed_check_points", {}
            ):
                missed = entry.payload["missed_check_points"][drawing]
        return missed


GITHUB_COMMENT_LIMIT = 65_536
LINE_CHARS = 1_000
MAX_SEND_CHARS = 63_000


def payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(", ", ": "))


def check_size(payload: dict[str, Any]) -> None:
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

    def save_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry: ...

    def save_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry: ...

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None: ...

    def save_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry: ...

    def save_self_assessment(
        self, student: Student, competency: str, levels: dict[str, Any]
    ) -> Entry: ...

    def save_evidence_plan(
        self, student: Student, competency: str, plan: dict[str, Any]
    ) -> Entry: ...

    def save_declaration(
        self, student: Student, declaration: dict[str, Any]
    ) -> Entry: ...

    def records(self, students: list[Student]) -> list[Record]: ...

    def save_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry: ...

    def save_evidence_panel_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry: ...
