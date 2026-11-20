"""The Evidence panel's and the Evidence Project's routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app import evidence_panel
from app.auth import current_student
from app.evidence_panel import Declaration, EvidencePanel, NotAProject
from app.roster import Student
from app.settings import Settings

from .evidence import (
    _competency,
    _declaration_out,
    _declaration_payload,
    _declared,
    _panel,
)
from .models import (
    DeclarationIn,
    ProjectIn,
)
from .router import router
from .steps import (
    _refuse_after_the_reading_day,
    _store,
)


@router.get("/api/competencies/{competency}/evidence-panel", tags=["rehearsal"])
def evidence_panel_view(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> EvidencePanel:
    """What the Reading Day would find on the Student's Evidence Project today for
    this Competency: facts, never a Band."""
    c = _competency(request, competency, student)
    declared = _store(request).record(student).declaration()
    return _panel(
        request, student, c, _declaration_out(declared, request, student), refresh=False
    )


@router.post(
    "/api/competencies/{competency}/evidence-panel/refresh", tags=["rehearsal"]
)
def refresh_evidence_panel(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> EvidencePanel:
    """Check the Evidence Project for a push since its last reading, and recompute what
    moved. Stores nothing in the record."""
    c = _competency(request, competency, student)
    declared = _store(request).record(student).declaration()
    return _panel(
        request, student, c, _declaration_out(declared, request, student), refresh=True
    )


@router.post("/api/evidence-project/check", tags=["rehearsal"])
def check_project_access(
    sent: ProjectIn,
    request: Request,
    student: Student = Depends(current_student),
) -> evidence_panel.Access:
    """Whether the Reading Day could read this project, before declaring it. Stores
    nothing."""
    try:
        project = evidence_panel.parse_project(sent.url)
    except NotAProject as error:
        raise HTTPException(422, str(error)) from error
    settings: Settings = request.app.state.settings
    return evidence_panel.access(
        project,
        student.evidence_project,
        request.app.state.access_check,
        settings.github_app_slug,
    )


@router.post("/api/evidence-project/declaration", tags=["rehearsal"])
def declare_evidence_project(
    sent: DeclarationIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Declaration:
    """Declare (or change) the Evidence Project of every Competency, until the Reading
    Day."""
    declaration = _declaration_payload(request, student, sent)
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Project")
    entry = _store(request).save_declaration(student, declaration)
    return _declared(entry.payload, entry.at, request, student)


@router.delete("/api/evidence-project/declaration", tags=["rehearsal"])
def withdraw_evidence_project(
    request: Request, student: Student = Depends(current_student)
) -> None:
    """Withdraw the Evidence Project declared: the Reading Day reads the roster's
    again."""
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Project")
    store = _store(request)
    if store.record(student).declaration() is None:
        raise HTTPException(409, "No other Evidence Project is declared")
    store.save_declaration(student, {})
