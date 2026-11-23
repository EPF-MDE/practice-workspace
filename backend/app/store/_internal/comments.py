from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.roster import Student
from app.store._internal.model import LINE_CHARS, Entry
from app.store._internal.payloads import (
    AnswerPayload,
    CheckPointsPayload,
    DeclarationPayload,
    DrawingPayload,
    EvidencePanelSnapshotPayload,
    EvidencePlanPayload,
    Kind,
    Payload,
    QuestionPayload,
    SelfAssessmentPayload,
    UnreadablePayload,
    WithdrawalPayload,
    read_payload,
)

FENCE = "json practice"
_BLOCK = re.compile(r"^```json practice\n(\{.*\})\n```$", re.MULTILINE)
_MARKER = "<!-- practice-student-id: {} -->"
_MARKER_RE = re.compile(r"<!-- practice-student-id: (\d+) -->")
_KEY_NAME: dict[str, str] = {
    Kind.ANSWER: "step",
    Kind.QUESTION: "step",
    Kind.DRAWING: "drawing",
    Kind.CHECK_POINTS: "drawing",
}


def _line(
    competency: str | None, key: str | None, version: int, payload: Payload
) -> str:
    v = f"(version {version})"
    match payload:
        case AnswerPayload():
            return f"**Answer** to {competency}, step `{key}` {v}"
        case QuestionPayload(text=text):
            quoted = "\n".join(f"> {line}" for line in text.splitlines())
            return f"**Question** at {competency}, step `{key}`:\n\n{quoted}"
        case DrawingPayload():
            return (
                f"**Drawing** `{key}` for {competency} {v}: `{payload.png}` "
                f"({payload.png_bytes:,} bytes), "
                f"`{payload.snapshot}` ({payload.snapshot_bytes:,} bytes)"
            )
        case CheckPointsPayload(missed=missed):
            return (
                f"**Check points missed** on drawing `{key}`, "
                f"{competency} {v}: {', '.join(missed) or 'none'}"
            )
        case SelfAssessmentPayload(levels=levels):
            rated = ", ".join(f"{point} {it.level}" for point, it in levels.items())
            return (
                f"**Self-assessment** of {competency} {v}: {rated or 'no point rated'}"
            )
        case EvidencePlanPayload():
            confirmed = ", confirmed at the closing step" if payload.confirmed else ""
            confirmed += ", the draft untouched" if payload.drafted else ""
            snapshot = (
                ", with the Evidence panel as shown"
                if payload.evidence_panel_snapshot is not None
                else ""
            )
            declared = payload.declaration
            evidence = (
                f"; **Evidence Project** declared: {declared.url}" if declared else ""
            )
            return (
                f"**Evidence Plan** for {competency} {v}{confirmed}{snapshot}{evidence}"
            )
        case DeclarationPayload():
            return f"**Evidence Project** declared for every Competency {v}"
        case WithdrawalPayload():
            return f"**Evidence Project** withdrawn for every Competency {v}"
        case EvidencePanelSnapshotPayload():
            return f"**Evidence panel** as seen at {competency}'s closing step {v}"
    raise ValueError(payload)


def comment_body(
    competency: str | None, key: str | None, version: int, payload: Payload
) -> str:
    block: dict[str, Any] = {"kind": payload.KIND, "competency": competency}
    if payload.KIND in _KEY_NAME:
        block[_KEY_NAME[payload.KIND]] = key
    block |= {"version": version, "payload": payload.stored()}
    data = json.dumps(block, ensure_ascii=False, separators=(", ", ": "))
    line = _line(competency, key, version, payload)
    if len(line) > LINE_CHARS:
        line = line[: LINE_CHARS - 1] + "…"
    return f"{line}\n\n```{FENCE}\n{data}\n```\n"


def _entry(comment: dict[str, Any], bot_login: str) -> Entry[Payload] | None:
    user = comment.get("user") or {}
    if user.get("type") != "Bot" or user.get("login") != bot_login:
        return None
    match = _BLOCK.search(comment.get("body") or "")
    if match is None:
        return None
    block = json.loads(match[1])
    try:
        kind = Kind(block["kind"])
        payload = read_payload(kind, block["payload"])
    except (ValueError, UnreadablePayload):
        return None
    key = block.get(_KEY_NAME[kind]) if kind in _KEY_NAME else None
    return Entry(
        block["competency"],
        key,
        payload,
        block["version"],
        _time(comment["created_at"]),
    )


def _renumbered(entries: list[Entry[Payload]]) -> list[Entry[Payload]]:
    seen: dict[tuple[Any, ...], int] = {}
    out = []
    for entry in entries:
        key = (entry.kind, entry.competency, entry.key)
        seen[key] = seen.get(key, 0) + 1
        out.append(
            entry if entry.version == seen[key] else replace(entry, version=seen[key])
        )
    return out


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _header(student: Student) -> str:
    return (
        f"{_MARKER.format(student.github_id)}\n"
        f"**Student:** {student.name} (`{student.github_login}`)\n"
        f"**Group:** {student.group}\n"
        f"**Evidence Project:** [{student.evidence_project}](https://github.com/{student.evidence_project})\n\n"
        "Each comment below is one send from the Practice workspace: a line to read, "
        f"then a `{FENCE}` block the workspace reads back. Comments by people are "
        "ignored by it.\n"
    )
