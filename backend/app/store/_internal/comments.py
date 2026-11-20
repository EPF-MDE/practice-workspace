"""How a send is written in an issue comment, and read back from one."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.roster import Student
from app.store._internal.model import (
    LINE_CHARS,
    Entry,
    Kind,
)

FENCE = "json rehearsal"
_BLOCK = re.compile(r"^```json rehearsal\n(\{.*\})\n```$", re.MULTILINE)
_MARKER = "<!-- rehearsal-student-id: {} -->"
_MARKER_RE = re.compile(r"<!-- rehearsal-student-id: (\d+) -->")
# The name the block gives an entry's key, per kind; other kinds have none.
_KEY_NAME: dict[str, str] = {
    Kind.ANSWER: "step",
    Kind.QUESTION: "step",
    Kind.DRAWING: "drawing",
    Kind.CHECK_POINTS: "drawing",
}


def _line(
    kind: str, competency: str, key: str | None, version: int, payload: dict[str, Any]
) -> str:
    """The comment's first line, for a person reading the issue."""
    v = f"(version {version})"
    match kind:
        case Kind.ANSWER:
            return f"**Answer** to {competency}, step `{key}` {v}"
        case Kind.QUESTION:
            quoted = "\n".join(f"> {line}" for line in payload["text"].splitlines())
            return f"**Question** at {competency}, step `{key}`:\n\n{quoted}"
        case Kind.DRAWING:
            return (
                f"**Drawing** `{key}` for {competency} {v}: `{payload['png']}` "
                f"({payload['png_bytes']:,} bytes), "
                f"`{payload['snapshot']}` ({payload['snapshot_bytes']:,} bytes)"
            )
        case Kind.CHECK_POINTS:
            missed = ", ".join(payload["missed"]) or "none"
            return (
                f"**Check points missed** on drawing `{key}`, "
                f"{competency} {v}: {missed}"
            )
        case Kind.SELF_ASSESSMENT:
            levels = ", ".join(
                f"{point} {rated['level']}"
                for point, rated in payload.get("levels", {}).items()
            )
            return (
                f"**Self-assessment** of {competency} {v}: {levels or 'no point rated'}"
            )
        case Kind.EVIDENCE_PLAN:
            confirmed = (
                ", confirmed at the closing step" if payload.get("confirmed") else ""
            )
            confirmed += ", the draft untouched" if payload.get("drafted") else ""
            # The closing step's one send also carries the Evidence panel shown and any
            # declaration made there.
            snapshot = (
                ", with the Evidence panel as shown"
                if "evidence_panel_snapshot" in payload
                else ""
            )
            declared = payload.get("declaration")
            evidence = (
                f"; **Evidence Project** declared: {declared['url']}"
                if declared
                else ""
            )
            return (
                f"**Evidence Plan** for {competency} {v}{confirmed}{snapshot}{evidence}"
            )
        case Kind.DECLARATION:
            what = "withdrawn" if not payload else "declared"
            return f"**Evidence Project** {what} for {competency} {v}"
        case Kind.EVIDENCE_PANEL_SNAPSHOT:
            return f"**Evidence panel** as seen at {competency}'s closing step {v}"
    raise ValueError(kind)


def comment_body(
    entry_kind: str,
    competency: str,
    key: str | None,
    version: int,
    payload: dict[str, Any],
) -> str:
    block: dict[str, Any] = {"kind": entry_kind, "competency": competency}
    if entry_kind in _KEY_NAME:
        block[_KEY_NAME[entry_kind]] = key
    block |= {"version": version, "payload": payload}
    data = json.dumps(block, ensure_ascii=False, separators=(", ", ": "))
    line = _line(entry_kind, competency, key, version, payload)
    if len(line) > LINE_CHARS:  # a long question: the block below holds it whole
        line = line[: LINE_CHARS - 1] + "…"
    return f"{line}\n\n```{FENCE}\n{data}\n```\n"


def _entry(comment: dict[str, Any], bot_login: str) -> Entry | None:
    """The entry a comment holds, or None for a comment that is not a send (not by the
    Store App)."""
    user = comment.get("user") or {}
    if user.get("type") != "Bot" or user.get("login") != bot_login:
        return None
    match = _BLOCK.search(comment.get("body") or "")
    if match is None:
        return None
    block = json.loads(match[1])
    try:
        kind = Kind(block["kind"])
    except ValueError:  # a kind this version does not know: not a send it can read
        return None
    key = block.get(_KEY_NAME[kind]) if kind in _KEY_NAME else None
    return Entry(
        kind,
        block["competency"],
        key,
        block["payload"],
        block["version"],
        _time(comment["created_at"]),
    )


def _renumbered(entries: list[Entry]) -> list[Entry]:
    """Versions counted again in date order: two issues may each hold a version 1 of the
    same thing."""
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
        "Each comment below is one send from the Rehearsal workspace: a line to read, "
        f"then a `{FENCE}` block the workspace reads back. Comments by people are "
        "ignored by it.\n"
    )
