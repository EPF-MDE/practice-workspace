"""The Store's interface and its domain types; see the package's docstring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from app.roster import Student


class Kind(StrEnum):
    """What a send is: one set, for the Store and its callers alike."""

    ANSWER = "answer"  # key: the step id. payload: {"fields": {field id: text}}
    # key: the drawing id (its step's). payload: drawing_payload() (+ "commit" on
    # GitHub)
    DRAWING = "drawing"
    CHECK_POINTS = (
        "check-points"  # key: the drawing id. payload: {"missed": [check point id]}
    )
    # key: None. payload: {"levels": {point id: {"level", "link"}},
    # "missed_check_points"?: {drawing: [id]}}
    SELF_ASSESSMENT = "self-assessment"
    # key: None. payload: {"text", "example"?, "confirmed"?, "drafted"?}; the closing
    # step's one send also carries "evidence_panel_snapshot" and, when declared
    # there, "declaration"
    EVIDENCE_PLAN = "evidence-plan"
    # competency: EVERY_COMPETENCY, key: None. payload: StoredDeclaration's fields but
    # `at`, or {} when withdrawn
    DECLARATION = "declaration"
    # key: the step id. payload: {"text": ...}. Every question counts, not only the
    # latest.
    QUESTION = "question"
    # key: None. payload: the Evidence panel as the Student saw it
    EVIDENCE_PANEL_SNAPSHOT = "evidence-panel-snapshot"


KINDS: tuple[Kind, ...] = tuple(Kind)

# The competency of an entry that is for every Competency: a declaration.
EVERY_COMPETENCY = None


@dataclass(frozen=True)
class Entry:
    """One send: what, for which Competency and step (or drawing, or none), and when."""

    kind: Kind
    # "C1", "C2", "C3"; EVERY_COMPETENCY (None) for a declaration
    competency: str | None
    key: str | None  # the step or drawing id; None for a per-Competency kind
    payload: dict[str, Any]  # JSON-safe
    version: int  # 1, 2... per (kind, competency, key)
    at: datetime  # when it was stored, timezone-aware


# Where a declared Evidence Project is hosted.
Host = Literal["github", "gitlab"]
GITHUB: Host = "github"
GITLAB: Host = "gitlab"
_HOSTS: dict[str, Host] = {GITHUB: GITHUB, GITLAB: GITLAB}


@dataclass(frozen=True)
class StoredDeclaration:
    """An Evidence Project declared for every Competency, as stored, and when."""

    url: str
    note: str  # what to read
    repository: str  # "owner/name"; on GitLab, the project's full path
    host: Host
    access: str  # its access as checked when declared
    at: datetime

    @classmethod
    def from_payload(cls, payload: dict[str, Any], at: datetime) -> StoredDeclaration:
        return cls(
            url=payload["url"],
            note=payload["note"],
            repository=payload["repository"],
            host=_HOSTS[payload["host"]],
            access=payload["access"],
            at=at,
        )


@dataclass(frozen=True)
class DrawingFiles:
    png: bytes
    snapshot: dict[str, Any]  # the tldraw snapshot, JSON


DRAWINGS_FOLDER = "drawings"


def drawing_paths(student: Student, competency: str, drawing: str) -> tuple[str, str]:
    """Where a drawing's PNG and snapshot live on `workspace-data`: per Student,
    Competency and drawing.

    Every version goes to the same two paths, so Git history keeps them all.
    """
    base = f"{DRAWINGS_FOLDER}/{student.github_login}/{competency}/{drawing}"
    return f"{base}.png", f"{base}.snapshot.json"


def snapshot_file(snapshot: dict[str, Any]) -> bytes:
    """The snapshot as stored: compact UTF-8 JSON."""
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def drawing_payload(
    student: Student, competency: str, drawing: str, png: bytes, snapshot: bytes
) -> dict[str, Any]:
    """A `drawing` entry's payload: where its files are, and their sizes in bytes."""
    png_path, snapshot_path = drawing_paths(student, competency, drawing)
    return {
        "png": png_path,
        "png_bytes": len(png),
        "snapshot": snapshot_path,
        "snapshot_bytes": len(snapshot),
    }


@dataclass(frozen=True)
class Record:
    """A Student's record: all their sends, oldest first."""

    student: Student
    entries: tuple[Entry, ...] = ()

    def history(
        self, kind: Kind, competency: str | None, key: str | None = None
    ) -> list[Entry]:
        """Every version of one thing, oldest first."""
        return [
            e
            for e in self.entries
            if (e.kind, e.competency, e.key) == (kind, competency, key)
        ]

    def latest(
        self, kind: Kind, competency: str | None, key: str | None = None
    ) -> Entry | None:
        """The current state of one thing: its latest version, or None if never sent."""
        versions = self.history(kind, competency, key)
        return versions[-1] if versions else None

    def all(self, kind: Kind, competency: str | None = None) -> list[Entry]:
        """Every entry of a kind (e.g. every question), in one Competency or all."""
        return [
            e
            for e in self.entries
            if e.kind == kind and competency in (None, e.competency)
        ]

    def declaration(self) -> StoredDeclaration | None:
        """The Evidence Project declared now for every Competency, and when: sent alone,
        or with any closing step's Evidence Plan. None if never declared, or withdrawn
        since (an empty declaration)."""
        found: tuple[dict[str, Any], datetime] | None = None
        for entry in self.entries:
            if entry.kind == Kind.DECLARATION:
                found = (entry.payload, entry.at) if entry.payload else None
            elif entry.kind == Kind.EVIDENCE_PLAN and "declaration" in entry.payload:
                found = (entry.payload["declaration"], entry.at)
        return None if found is None else StoredDeclaration.from_payload(*found)

    def missed_check_points(self, competency: str, drawing: str) -> list[str] | None:
        """The check points last ticked as missed on a drawing: sent alone, or with a
        Self-assessment. None if never ticked."""
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


# GitHub refuses a comment body over 65,536 characters. A send's payload, as JSON, stays
# under this, leaving room for the comment's line to read (at most LINE_CHARS) and the
# block around the payload.
GITHUB_COMMENT_LIMIT = 65_536
LINE_CHARS = 1_000
MAX_SEND_CHARS = 63_000


def payload_json(payload: dict[str, Any]) -> str:
    """A payload as the Store writes it: one line of JSON, UTF-8 kept, escapes
    counted."""
    return json.dumps(payload, ensure_ascii=False, separators=(", ", ": "))


def check_size(payload: dict[str, Any]) -> None:
    """Refuse a send too large for one comment, before anything is written."""
    if len(payload_json(payload)) > MAX_SEND_CHARS:
        raise SendTooLarge(
            f"a send holds at most {MAX_SEND_CHARS:,} characters of JSON"
        )


class SendTooLarge(ValueError):
    """The send is too large to store as one: the caller should refuse it (422), not
    retry it."""


class StoreUnavailable(RuntimeError):
    """The Store could not read or write (GitHub down or rate-limited): try again."""


class Store(Protocol):
    """Where the Practice's sends live. One instance for the whole app."""

    def open_record(self, student: Student) -> None:
        """At sign-in: make the Student's record ready (the GitHub Store opens their
        issue once)."""
        ...

    def record(self, student: Student) -> Record:
        """Read a Student's record (empty before their first send)."""
        ...

    def save_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry:
        """Save the Student's answer to a step: one text per field."""
        ...

    def save_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry:
        """Save a drawing: its PNG and its tldraw snapshot. A new version replaces the
        files."""
        ...

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None:
        """The latest version of a drawing's files, or None if never sent."""
        ...

    def save_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry:
        """Save which check points of the Reference Drawing the Student's drawing
        missed."""
        ...

    def save_self_assessment(
        self, student: Student, competency: str, levels: dict[str, Any]
    ) -> Entry:
        """Save the Self-assessment: per point id, its level and, for "I have done it",
        its link."""
        ...

    def save_evidence_plan(
        self, student: Student, competency: str, plan: dict[str, Any]
    ) -> Entry:
        """Save the Evidence Plan as it stands (the Student's text wins once edited)."""
        ...

    def save_declaration(self, student: Student, declaration: dict[str, Any]) -> Entry:
        """Save the Evidence Project declared for every Competency; `{}` withdraws
        it."""
        ...

    def records(self, students: list[Student]) -> list[Record]:
        """Read every given Student's record at once, in their order."""
        ...

    def save_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry:
        """Save a question asked at a step."""
        ...

    def save_evidence_panel_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry:
        """Save the Evidence panel as the Student saw it at a Competency's closing
        step."""
        ...
