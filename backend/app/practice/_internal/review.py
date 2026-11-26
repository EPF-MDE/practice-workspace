from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app import closing
from app.content import (
    Page,
    Point,
)
from app.store import (
    AnswerPayload,
    DrawingPayload,
    Entry,
    EvidencePlanPayload,
    PointLevelPayload,
    Record,
    SelfAssessmentPayload,
)

from .models import (
    EvidencePlan,
    EvidencePlanVersion,
    PointLevel,
    PointLevelNow,
    SelfAssessment,
    SelfAssessmentVersion,
)


def _points(page: Page) -> list[Point]:
    return [b for step in page.steps for b in step.blocks if isinstance(b, Point)]


def _since(
    dated: list[tuple[dict[str, PointLevelPayload], datetime]], point: str
) -> datetime:
    at = closing.since(dated, point)
    assert at is not None
    return at


def _self_assessment(record: Record, competency: str) -> SelfAssessment | None:
    history = record.history(SelfAssessmentPayload, competency)
    if not history:
        return None
    dated = [(e.payload.levels, e.at) for e in history]
    latest = history[-1]
    return SelfAssessment(
        levels={
            point: PointLevelNow(
                level=level.level, link=level.link, since=_since(dated, point)
            )
            for point, level in latest.payload.levels.items()
        },
        version=latest.version,
        sent_at=latest.at,
        history=[
            SelfAssessmentVersion(
                levels={
                    point: PointLevel(level=level.level, link=level.link)
                    for point, level in e.payload.levels.items()
                },
                version=e.version,
                sent_at=e.at,
            )
            for e in history
        ],
    )


def _levels_now(record: Record, competency: str) -> dict[str, PointLevelPayload]:
    assessment = record.latest(SelfAssessmentPayload, competency)
    return assessment.payload.levels if assessment else {}


def _plan_version(entry: Entry[EvidencePlanPayload]) -> EvidencePlanVersion:
    return EvidencePlanVersion(
        text=entry.payload.text,
        drafted=entry.payload.drafted,
        example=entry.payload.example,
        confirmed=entry.payload.confirmed,
        version=entry.version,
        sent_at=entry.at,
    )


def _evidence_plan(record: Record, competency: str) -> EvidencePlan | None:
    history = record.history(EvidencePlanPayload, competency)
    if not history:
        return None
    return EvidencePlan(
        **_plan_version(history[-1]).model_dump(),
        history=[_plan_version(e) for e in history],
    )


def _evidence_project(record: Record) -> str | None:
    declared = record.declaration()
    return declared.url if declared else None


def _transfer(page: Page, record: Record) -> closing.Transfer | None:
    for step in page.steps:
        sent = (
            record.latest(AnswerPayload, page.competency, step.id)
            if step.kind == "transfer" and step.fills
            else None
        )
        if sent is None or step.fills is None:
            continue
        fields = sent.payload.fields
        project = (
            fields.get("project", "").strip()
            or _evidence_project(record)
            or "my Evidence Project"
        )
        plan = "; ".join(
            text.strip()
            for field, text in fields.items()
            if field != "project" and text.strip()
        )
        return closing.Transfer(step.fills, project, plan)
    return None


def _draft(
    page: Page,
    record: Record,
    levels: dict[str, PointLevelPayload],
    scale: closing.Scale,
) -> str:
    return closing.draft(
        _points(page),
        levels,
        scale,
        _transfer(page, record),
        _evidence_project(record),
    )


def _drafted(
    page: Page, record: Record, text: str, flagged: bool, scale: closing.Scale
) -> bool:
    levels = _levels_now(record, page.competency)
    return flagged or text.strip() == _draft(page, record, levels, scale).strip()


def _levels(
    page: Page, levels: dict[str, PointLevel], scale: closing.Scale
) -> dict[str, PointLevelPayload]:
    try:
        return closing.clean_levels(
            {p: v.model_dump() for p, v in levels.items()},
            [p.id for p in _points(page)],
            scale,
        )
    except closing.Refused as refused:
        raise HTTPException(refused.status, refused.message) from refused


def _ticks(
    page: Page, record: Record, sent: dict[str, list[str]], phase: closing.Phase
) -> dict[str, list[str]]:
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
        if record.latest(DrawingPayload, page.competency, drawing) is None:
            raise HTTPException(
                409,
                "Send your drawing first: the check points come with the Reference "
                "Drawing",
            )
        ticks[drawing] = [c for c in known if c in missed]
        if phase.after_the_close and ticks[drawing] != (
            record.missed_check_points(page.competency, drawing) or []
        ):
            raise HTTPException(
                403,
                "The workspace has closed: the check points you ticked can no longer "
                "change.",
            )
    return ticks
