"""The closing step's routes: Self-assessment, Practice Plan, example for the Eval."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from app import closing, fork_panel
from app.auth import current_student
from app.roster import Student
from app.settings import Settings
from app.store import Kind

from .evidence import (
    _changed,
    _declaration_out,
    _declaration_payload,
    _panel,
)
from .models import (
    MAX_EXAMPLE_CHARS,
    MAX_PLAN_CHARS,
    ClosingIn,
    Draft,
    LevelsIn,
    PracticePlanIn,
    PracticePlanVersion,
    SelfAssessmentIn,
    Stored,
    _at_most,
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


@router.post("/api/competencies/{competency}/self-assessment", tags=["rehearsal"])
def send_self_assessment(
    competency: str,
    sent: SelfAssessmentIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Stored:
    """Store the Self-assessment: one level per point rated, a link for "I have done
    it", and the missed check points this browser kept since the drawing was sent."""
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


@router.post("/api/competencies/{competency}/practice-plan/draft", tags=["rehearsal"])
def draft_practice_plan(
    competency: str,
    sent: LevelsIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Draft:
    """The Practice Plan drafted from levels not sent yet, as the Student rates. Stores
    nothing."""
    page = _page(request, competency, student)
    levels = _levels(page, sent.levels) if sent.levels else {}
    return Draft(text=_draft(page, _store(request).record(student), levels))


@router.post("/api/competencies/{competency}/practice-plan", tags=["rehearsal"])
def send_practice_plan(
    competency: str,
    sent: PracticePlanIn,
    request: Request,
    student: Student = Depends(current_student),
) -> PracticePlanVersion:
    """Store the Student's own Practice Plan text, a new dated version; it wins over the
    draft. The example for the Eval and the confirmation carry over from the closing
    step."""
    page = _page(request, competency, student)
    _at_most(sent.text, MAX_PLAN_CHARS, "Your Practice Plan")
    _refuse_after_the_reading_day(request.app.state.settings, "your Practice Plan")
    store = _store(request)
    record = store.record(student)
    latest = record.latest(Kind.PRACTICE_PLAN, competency)
    carried = {
        k: latest.payload[k]
        for k in ("example", "confirmed")
        if latest and k in latest.payload
    }
    drafted = _drafted(page, record, sent.text, sent.drafted)
    entry = store.save_practice_plan(
        student, competency, {"text": sent.text} | drafted | carried
    )
    return _plan_version(entry)


@router.post("/api/competencies/{competency}/close", tags=["rehearsal"])
def close_competency(
    competency: str,
    sent: ClosingIn,
    request: Request,
    student: Student = Depends(current_student),
) -> PracticePlanVersion:
    """The closing step, one send: the Practice Plan confirmed, with one example for the
    Eval, the Evidence Project declared there if any, and a snapshot of the fork panel
    as shown."""
    page = _page(request, competency, student)
    if not sent.example.strip():
        raise HTTPException(422, "Write one example you will show at the Eval")
    _at_most(sent.text, MAX_PLAN_CHARS, "Your Practice Plan")
    _at_most(sent.example, MAX_EXAMPLE_CHARS, "Your example for the Eval")
    declaration = (
        _declaration_payload(request, student, sent.declaration)
        if sent.declaration
        else None
    )
    _refuse_after_the_reading_day(request.app.state.settings, "your Practice Plan")
    store = _store(request)
    record = store.record(student)
    if record.latest(Kind.SELF_ASSESSMENT, competency) is None:
        raise HTTPException(
            409, "Send your Self-assessment first: the Practice Plan is drafted from it"
        )
    plan: dict[str, Any] = {
        "text": sent.text,
        "example": sent.example.strip(),
        "confirmed": True,
    }
    plan |= _drafted(page, record, sent.text, sent.drafted)
    current = record.declaration(competency)
    if declaration and (current is None or _changed(current[0], declaration)):
        plan["declaration"] = declaration
        current = (declaration, _now())
    panel = _panel(
        request,
        student,
        competency,
        _declaration_out(current, request, student),
        refresh=False,
    )
    plan["fork_snapshot"] = fork_panel.snapshot(panel)
    return _plan_version(store.save_practice_plan(student, competency, plan))
