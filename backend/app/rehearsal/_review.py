"""The closing step's parts: Self-assessment, Practice Plan, example for the Eval."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app import closing
from app.content import (
    Page,
    Point,
)
from app.store import Entry, Kind, Record

from ._models import (
    MAX_URL_CHARS,
    PointLevel,
    PointLevelNow,
    PracticePlan,
    PracticePlanVersion,
    SelfAssessment,
    SelfAssessmentVersion,
    _at_most,
)

# --- The closing step: Self-assessment, Practice Plan, example for the Eval --


def _points(page: Page) -> list[Point]:
    return [b for step in page.steps for b in step.blocks if isinstance(b, Point)]


def _since(
    dated: list[tuple[dict[str, dict[str, Any]], datetime]], point: str
) -> datetime:
    """When a point of the latest version took its level: always found."""
    at = closing.since(dated, point)
    assert at is not None
    return at


def _self_assessment(record: Record, competency: str) -> SelfAssessment | None:
    history = record.history(Kind.SELF_ASSESSMENT, competency)
    if not history:
        return None
    dated = [(e.payload["levels"], e.at) for e in history]
    latest = history[-1]
    return SelfAssessment(
        levels={
            point: PointLevelNow(**level, since=_since(dated, point))
            for point, level in latest.payload["levels"].items()
        },
        version=latest.version,
        sent_at=latest.at,
        history=[
            SelfAssessmentVersion(
                levels=e.payload["levels"], version=e.version, sent_at=e.at
            )
            for e in history
        ],
    )


def _plan_version(entry: Entry) -> PracticePlanVersion:
    return PracticePlanVersion(
        text=entry.payload["text"],
        drafted=entry.payload.get("drafted", False),
        example=entry.payload.get("example"),
        confirmed=entry.payload.get("confirmed", False),
        version=entry.version,
        sent_at=entry.at,
    )


def _practice_plan(record: Record, competency: str) -> PracticePlan | None:
    history = record.history(Kind.PRACTICE_PLAN, competency)
    if not history:
        return None
    return PracticePlan(
        **_plan_version(history[-1]).model_dump(),
        history=[_plan_version(e) for e in history],
    )


def _evidence_project(record: Record, competency: str) -> str | None:
    declared = record.declaration(competency)
    return declared[0]["url"] if declared else None


def _transfer(page: Page, record: Record) -> closing.Transfer | None:
    """The Transfer the Student sent, if any: it fills its point's "To get there"."""
    for step in page.steps:
        sent = (
            record.latest(Kind.ANSWER, page.competency, step.id)
            if step.kind == "transfer" and step.fills
            else None
        )
        if sent is None or step.fills is None:
            continue
        fields = sent.payload["fields"]
        project = (
            fields.get("project", "").strip()
            or _evidence_project(record, page.competency)
            or "my Evidence Project"
        )
        plan = "; ".join(
            text.strip()
            for field, text in fields.items()
            if field != "project" and text.strip()
        )
        return closing.Transfer(step.fills, project, plan)
    return None


def _draft(page: Page, record: Record, levels: dict[str, Any]) -> str:
    return closing.draft(
        _points(page),
        levels,
        _transfer(page, record),
        _evidence_project(record, page.competency),
    )


def _drafted(page: Page, record: Record, text: str, flagged: bool) -> dict[str, bool]:
    """`{"drafted": True}` when the text sent is the draft untouched (the browser says
    so, or it matches the draft from the levels stored): it stays a draft. Only an edit
    makes it the Student's text."""
    assessment = record.latest(Kind.SELF_ASSESSMENT, page.competency)
    levels = assessment.payload["levels"] if assessment else {}
    return (
        {"drafted": True}
        if flagged or text.strip() == _draft(page, record, levels).strip()
        else {}
    )


def _levels(page: Page, levels: dict[str, PointLevel]) -> dict[str, dict[str, Any]]:
    for point, level in levels.items():
        _at_most(level.link, MAX_URL_CHARS, f"The link for {point}")
    try:
        return closing.clean_levels(
            {p: v.model_dump() for p, v in levels.items()},
            [p.id for p in _points(page)],
        )
    except closing.Refused as refused:
        raise HTTPException(refused.status, refused.message) from refused


def _ticks(
    page: Page, record: Record, sent: dict[str, list[str]], phase: closing.Phase
) -> dict[str, list[str]]:
    """The missed check points riding with a Self-assessment, checked, in each
    reference's order."""
    ticks: dict[str, list[str]] = {}
    for drawing, missed in sent.items():
        step = page.step(drawing)
        reference = step.reference if step else None
        if reference is None:
            raise HTTPException(
                422, f"No drawing {drawing} with check points in {page.competency}"
            )
        known = [c.id for c in reference.check_points]
        unknown = set(missed) - set(known)
        if unknown:
            raise HTTPException(
                422, f"Not a check point of {drawing}: {', '.join(sorted(unknown))}"
            )
        if record.latest(Kind.DRAWING, page.competency, drawing) is None:
            raise HTTPException(
                409,
                "Send your drawing first: the check points come with the Reference "
                "Drawing",
            )
        ticks[drawing] = [c for c in known if c in missed]
        if phase != "open" and ticks[drawing] != (
            record.missed_check_points(page.competency, drawing) or []
        ):
            raise HTTPException(
                403,
                "The workspace has closed: the check points you ticked can no longer "
                "change.",
            )
    return ticks
