from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app import evidence_panel
from app.auth import current_student
from app.evidence_panel import Declaration, EvidencePanel, NotAProject
from app.roster import Student
from app.settings import Settings
from app.store import StoredDeclaration

from .evidence import (
    _competency,
    _declaration_payload,
    _declared,
)
from .models import (
    DeclarationIn,
    ProjectIn,
)
from .steps import (
    _refuse_after_the_reading_day,
    _store,
    _upstream,
)

router = APIRouter()


@router.get("/api/competencies/{competency}/evidence-panel", tags=["practice"])
def evidence_panel_view(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> EvidencePanel:
    return _read_panel(request, student, competency, refresh=False)


@router.post("/api/competencies/{competency}/evidence-panel/refresh", tags=["practice"])
def refresh_evidence_panel(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> EvidencePanel:
    return _read_panel(request, student, competency, refresh=True)


def _read_panel(
    request: Request, student: Student, competency: str, refresh: bool
) -> EvidencePanel:
    c = _competency(request, competency, student)
    declared = _store(request).record(student).declaration()
    return evidence_panel.read_panel(
        c,
        request.app.state.repository_reading,
        student,
        _upstream(request, student),
        None if declared is None else _declared(declared, request, student),
        refresh,
    )


@router.post("/api/evidence-project/check", tags=["practice"])
def check_project_access(
    sent: ProjectIn,
    request: Request,
    student: Student = Depends(current_student),
) -> evidence_panel.Access:
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


@router.post("/api/evidence-project/declaration", tags=["practice"])
def declare_evidence_project(
    sent: DeclarationIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Declaration:
    declaration = _declaration_payload(request, student, sent)
    _refuse_after_the_reading_day(request, "your Evidence Project")
    entry = _store(request).send_declaration(student, declaration)
    return _declared(
        StoredDeclaration.from_payload(entry.payload, entry.at), request, student
    )


@router.delete("/api/evidence-project/declaration", tags=["practice"])
def withdraw_evidence_project(
    request: Request, student: Student = Depends(current_student)
) -> None:
    _refuse_after_the_reading_day(request, "your Evidence Project")
    store = _store(request)
    if store.record(student).declaration() is None:
        raise HTTPException(409, "No other Evidence Project is declared")
    store.withdraw_declaration(student)
