from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from typing import Any

from app.content import Point
from app.store import PointLevelPayload


class Phase(Enum):
    BEFORE_THE_CLOSE = "before-the-close"
    AFTER_THE_CLOSE = "after-the-close"
    AFTER_THE_READING_DAY = "after-the-reading-day"

    @property
    def after_the_close(self) -> bool:
        return self is not Phase.BEFORE_THE_CLOSE

    @property
    def after_the_reading_day(self) -> bool:
        return self is Phase.AFTER_THE_READING_DAY


_LINK = re.compile(r"https://(github\.com|gitlab\.com)/[\w.-]+/[\w.-]+(/\S*)?")


@dataclass(frozen=True)
class Level:
    id: str
    label: str


@dataclass(frozen=True)
class Scale:
    levels: tuple[Level, ...]

    @property
    def top(self) -> Level:
        return self.levels[-1]

    @property
    def below_top(self) -> tuple[str, ...]:
        return tuple(level.id for level in self.levels[:-1])

    def holds(self, level: str) -> bool:
        return any(known.id == level for known in self.levels)

    def label(self, level: str) -> str:
        return next((known.label for known in self.levels if known.id == level), level)

    def just_below_top(self, level: str) -> bool:
        return len(self.levels) > 1 and self.levels[-2].id == level


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def is_project_link(url: str | None) -> bool:
    if not url:
        return False
    return _LINK.fullmatch(url.strip()) is not None


def clean_levels(
    levels: dict[str, dict[str, Any]], point_ids: list[str], scale: Scale
) -> dict[str, PointLevelPayload]:
    unknown = [p for p in levels if p not in point_ids]
    if unknown:
        raise Refused(
            422, f"Not a point of this Competency: {', '.join(sorted(unknown))}"
        )
    if not levels:
        raise Refused(422, "Rate at least one point before sending")
    clean: dict[str, PointLevelPayload] = {}
    for point in point_ids:
        if point not in levels:
            continue
        level: str = levels[point]["level"]
        if not scale.holds(level):
            labels = ", ".join(known.label for known in scale.levels)
            raise Refused(422, f"{point}: the level is one of {labels}")
        link = (levels[point].get("link") or "").strip() or None
        if level == scale.top.id:
            if not is_project_link(link):
                raise Refused(
                    422,
                    f'{point}: "{scale.top.label}" needs a link to your work on '
                    "GitHub or GitLab (https://...)",
                )
        else:
            link = None
        clean[point] = PointLevelPayload(level=level, link=link)
    return clean


def check_move(
    previous: dict[str, PointLevelPayload],
    new: dict[str, PointLevelPayload],
    phase: Phase,
    scale: Scale,
) -> None:
    if not phase.after_the_close:
        return
    if phase.after_the_reading_day:
        raise Refused(
            403,
            "The Reading Day has passed: your Self-assessment can no longer change.",
        )
    rule = (
        "after the workspace closed, a level already given can only move up to "
        f'"{scale.top.label}", with a link'
    )
    for point, before in previous.items():
        after = new.get(point)
        if after is None:
            raise Refused(403, f"{point} is missing: {rule}.")
        if after != before and after.level != scale.top.id:
            raise Refused(
                403, f'{point} cannot move to "{scale.label(after.level)}": {rule}.'
            )


def since(
    history: list[tuple[dict[str, PointLevelPayload], datetime]], point: str
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
    levels: dict[str, PointLevelPayload],
    scale: Scale,
    transfer: Transfer | None = None,
    evidence_project: str | None = None,
) -> str:
    blocks = []
    for point in points:
        rated = levels.get(point.id)
        if rated is None or rated.level == scale.top.id:
            continue
        level = rated.level
        lines = [
            f"{point.id} ({point.band}), {scale.label(level)}: "
            f"{plain(point.statement_html)}"
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
        if scale.just_below_top(level):
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
