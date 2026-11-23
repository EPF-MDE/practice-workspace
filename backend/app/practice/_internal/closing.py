from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from app import closing, evidence_panel
from app.auth import current_student
from app.repository_reading import StudentToRead
from app.roster import Student
from app.settings import Settings
from app.store import Kind, StoredDeclaration

from .evidence import (
    _changed,
    _declaration_payload,
    _declared,
)
from .models import (
    ClosingIn,
    Draft,
    EvidencePlanIn,
    EvidencePlanVersion,
    LevelsIn,
    SelfAssessmentIn,
    Stored,
)
from .review import (
    _draft,
    _drafted,
    _levels,
    _plan_version,
    _ticks,
)
from .router import router
from .steps import (
    _now,
    _page,
    _phase,
    _refuse_after_the_reading_day,
    _store,
)


@router.post("/api/competencies/{competency}/self-assessment", tags=["practice"])
def send_self_assessment(
    competency: str,
    sent: SelfAssessmentIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Stored:
    page = _page(request, competency, student)
    levels = _levels(page, sent.levels)
    settings: Settings = request.app.state.settings
    phase = _phase(settings)
    _refuse_after_the_reading_day(settings, "your Self-assessment")
    store = _store(request)
    record = store.record(student)
    previous = record.latest(Kind.SELF_ASSESSMENT, competency)
    try:
        closing.check_move(
            previous.payload["levels"] if previous else {}, levels, phase
        )
    except closing.Refused as refused:
        raise HTTPException(refused.status, refused.message) from refused
    ticks = _ticks(page, record, sent.missed_check_points or {}, phase)
    payload: dict[str, Any] = {"levels": levels} | (
        {"missed_check_points": ticks} if ticks else {}
    )
    entry = store.save_self_assessment(student, competency, payload)
    return Stored(version=entry.version, sent_at=entry.at)


@router.post("/api/competencies/{competency}/evidence-plan/draft", tags=["practice"])
def draft_evidence_plan(
    competency: str,
    sent: LevelsIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Draft:
    page = _page(request, competency, student)
    levels = _levels(page, sent.levels) if sent.levels else {}
    return Draft(text=_draft(page, _store(request).record(student), levels))


@router.post("/api/competencies/{competency}/evidence-plan", tags=["practice"])
def send_evidence_plan(
    competency: str,
    sent: EvidencePlanIn,
    request: Request,
    student: Student = Depends(current_student),
) -> EvidencePlanVersion:
    page = _page(request, competency, student)
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Plan")
    store = _store(request)
    record = store.record(student)
    latest = record.latest(Kind.EVIDENCE_PLAN, competency)
    carried = {
        k: latest.payload[k]
        for k in ("example", "confirmed")
        if latest and k in latest.payload
    }
    drafted = _drafted(page, record, sent.text, sent.drafted)
    entry = store.save_evidence_plan(
        student, competency, {"text": sent.text} | drafted | carried
    )
    return _plan_version(entry)


@router.post("/api/competencies/{competency}/close", tags=["practice"])
def close_competency(
    competency: str,
    sent: ClosingIn,
    request: Request,
    student: Student = Depends(current_student),
) -> EvidencePlanVersion:
    page = _page(request, competency, student)
    if not sent.example.strip():
        raise HTTPException(422, "Write one example you will show at the Eval")
    declaration = (
        _declaration_payload(request, student, sent.declaration)
        if sent.declaration
        else None
    )
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Plan")
    store = _store(request)
    record = store.record(student)
    if record.latest(Kind.SELF_ASSESSMENT, competency) is None:
        raise HTTPException(
            409, "Send your Self-assessment first: the Evidence Plan is drafted from it"
        )
    plan: dict[str, Any] = {
        "text": sent.text,
        "example": sent.example.strip(),
        "confirmed": True,
    }
    plan |= _drafted(page, record, sent.text, sent.drafted)
    current = record.declaration()
    if declaration and (current is None or _changed(current, declaration)):
        plan["declaration"] = declaration
        current = StoredDeclaration.from_payload(declaration, _now())
    panel = evidence_panel.read_panel(
        competency,
        request.app.state.repository_reading,
        StudentToRead.from_roster(student),
        None if current is None else _declared(current, request, student),
    )
    plan["evidence_panel_snapshot"] = evidence_panel.snapshot(panel)
    return _plan_version(store.save_evidence_plan(student, competency, plan))
