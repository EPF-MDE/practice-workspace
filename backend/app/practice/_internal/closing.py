from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app import closing, evidence_panel
from app.auth import current_student
from app.roster import Student
from app.settings import Settings
from app.store import (
    EvidencePlanPayload,
    SelfAssessmentPayload,
    StoredDeclaration,
)

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
    _levels_now,
    _plan_version,
    _ticks,
)
from .router import router
from .steps import (
    _now,
    _page,
    _phase,
    _refuse_after_the_reading_day,
    _scale,
    _store,
    _student_to_read,
)


@router.post("/api/competencies/{competency}/self-assessment", tags=["practice"])
def send_self_assessment(
    competency: str,
    sent: SelfAssessmentIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Stored:
    page = _page(request, competency, student)
    scale = _scale(request)
    levels = _levels(page, sent.levels, scale)
    settings: Settings = request.app.state.settings
    phase = _phase(settings)
    _refuse_after_the_reading_day(settings, "your Self-assessment")
    store = _store(request)
    record = store.record(student)
    try:
        closing.check_move(_levels_now(record, competency), levels, phase, scale)
    except closing.Refused as refused:
        raise HTTPException(refused.status, refused.message) from refused
    ticks = _ticks(page, record, sent.missed_check_points or {}, phase)
    entry = store.send_self_assessment(
        student,
        competency,
        SelfAssessmentPayload(levels=levels, missed_check_points=ticks),
    )
    return Stored(version=entry.version, sent_at=entry.at)


@router.post("/api/competencies/{competency}/evidence-plan/draft", tags=["practice"])
def draft_evidence_plan(
    competency: str,
    sent: LevelsIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Draft:
    page = _page(request, competency, student)
    scale = _scale(request)
    levels = _levels(page, sent.levels, scale) if sent.levels else {}
    return Draft(text=_draft(page, _store(request).record(student), levels, scale))


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
    latest = record.latest(EvidencePlanPayload, competency)
    entry = store.send_evidence_plan(
        student,
        competency,
        EvidencePlanPayload(
            text=sent.text,
            drafted=_drafted(page, record, sent.text, sent.drafted, _scale(request)),
            example=latest.payload.example if latest else None,
            confirmed=latest.payload.confirmed if latest else False,
        ),
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
    if record.latest(SelfAssessmentPayload, competency) is None:
        raise HTTPException(
            409, "Send your Self-assessment first: the Evidence Plan is drafted from it"
        )
    current = record.declaration()
    changed = (
        declaration
        if declaration and (current is None or _changed(current, declaration))
        else None
    )
    if changed:
        current = StoredDeclaration.from_payload(changed, _now())
    panel = evidence_panel.read_panel(
        competency,
        request.app.state.repository_reading,
        _student_to_read(request, student),
        None if current is None else _declared(current, request, student),
    )
    plan = EvidencePlanPayload(
        text=sent.text,
        example=sent.example.strip(),
        confirmed=True,
        drafted=_drafted(page, record, sent.text, sent.drafted, _scale(request)),
        declaration=changed,
        evidence_panel_snapshot=evidence_panel.snapshot(panel),
    )
    return _plan_version(store.send_evidence_plan(student, competency, plan))
