from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Literal

from app.content import Point

Level = Literal["not-yet", "understand", "redo", "done"]
LEVELS: tuple[Level, ...] = ("not-yet", "understand", "redo", "done")
LABELS: dict[str, str] = {
    "not-yet": "Not yet",
    "understand": "I understand",
    "redo": "I can redo",
    "done": "I have done it",
}
Phase = Literal["open", "closed", "over"]

_LINK = re.compile(r"https://(github\.com|gitlab\.com)/[\w.-]+/[\w.-]+(/\S*)?")


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def phase(now: datetime, closes_at: datetime, reading_day_at: datetime) -> Phase:
    if now > reading_day_at:
        return "over"
    return "closed" if now > closes_at else "open"


def is_project_link(url: str | None) -> bool:
    if not url:
        return False
    return _LINK.fullmatch(url.strip()) is not None


def clean_levels(
    levels: dict[str, dict[str, Any]], point_ids: list[str]
) -> dict[str, dict[str, Any]]:
    unknown = [p for p in levels if p not in point_ids]
    if unknown:
        raise Refused(
            422, f"Not a point of this Competency: {', '.join(sorted(unknown))}"
        )
    if not levels:
        raise Refused(422, "Rate at least one point before sending")
    clean: dict[str, dict[str, Any]] = {}
    for point in point_ids:
        if point not in levels:
            continue
        level = levels[point].get("level")
        if level not in LEVELS:
            raise Refused(
                422, f"{point}: the level is one of {', '.join(LABELS.values())}"
            )
        link = (levels[point].get("link") or "").strip() or None
        if level == "done":
            if not is_project_link(link):
                raise Refused(
                    422,
                    f'{point}: "I have done it" needs a link to your work on GitHub or '
                    "GitLab (https://...)",
                )
        else:
            link = None
        clean[point] = {"level": level, "link": link}
    return clean


def check_move(
    previous: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]], now: Phase
) -> None:
    if now == "open":
        return
    if now == "over":
        raise Refused(
            403,
            "The Reading Day has passed: your Self-assessment can no longer change.",
        )
    rule = (
        "after the workspace closed, a level already given can only move up to "
        '"I have done it", with a link'
    )
    for point, before in previous.items():
        after = new.get(point)
        if after is None:
            raise Refused(403, f"{point} is missing: {rule}.")
        if after != before and after["level"] != "done":
            raise Refused(
                403, f'{point} cannot move to "{LABELS[after["level"]]}": {rule}.'
            )


def since(
    history: list[tuple[dict[str, dict[str, Any]], datetime]], point: str
) -> datetime | None:
    current = history[-1][0].get(point) if history else None
    if current is None:
        return None
    start = None
    for levels, at in history:
        start = (start or at) if levels.get(point) == current else None
    return start


@dataclass(frozen=True)
class Transfer:
    point: str
    project: str
    plan: str


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain(html: str | None) -> str:
    parser = _Text()
    parser.feed(html or "")
    return " ".join("".join(parser.parts).split())


def draft(
    points: list[Point],
    levels: dict[str, dict[str, Any]],
    transfer: Transfer | None = None,
    evidence_project: str | None = None,
) -> str:
    blocks = []
    for point in points:
        rated = levels.get(point.id)
        if rated is None or rated["level"] == "done":
            continue
        level = rated["level"]
        lines = [
            f"{point.id} ({point.band}), {LABELS[level]}: {plain(point.statement_html)}"
        ]
        if point.proof_html:
            lines.append(
                f"At the Eval, I will show {_uncapitalised(plain(point.proof_html))}"
            )
        if transfer and transfer.point == point.id:
            lines.append(
                f"To get there: carry out my Transfer, on {transfer.project}: "
                f"{transfer.plan}"
            )
        elif point.to_get_there_html.get(level):
            lines.append(f"To get there: {plain(point.to_get_there_html[level])}")
        if level == "redo":
            lines.append(
                "Where: my Evidence "
                f"Project{f' ({evidence_project})' if evidence_project else ''}."
            )
        else:
            lines.append(
                "Where: the course material, this page and the Worked Examples."
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _uncapitalised(text: str) -> str:
    return text if len(text) > 1 and text[1].isupper() else text[:1].lower() + text[1:]
