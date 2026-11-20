"""The fork panel's and the Evidence Project's routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app import fork_panel
from app.auth import current_student
from app.fork_panel import ForkPanel, NotAProject
from app.roster import Student
from app.settings import Settings

from .evidence import (
    _competency,
    _declaration_out,
    _declaration_payload,
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


@router.get("/api/competencies/{competency}/fork", tags=["rehearsal"])
def fork_panel_view(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> ForkPanel:
    """What the Reading Day would find on the Student's fork today for this Competency:
    facts, never a Band."""
    c = _competency(request, competency, student)
    declared = _store(request).record(student).declaration(c)
    return _panel(
        request, student, c, _declaration_out(declared, request, student), refresh=False
    )


@router.post("/api/competencies/{competency}/fork/refresh", tags=["rehearsal"])
def refresh_fork_panel(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> ForkPanel:
    """Check the fork for a push since its last reading, and recompute what moved.
    Stores nothing in the record."""
    c = _competency(request, competency, student)
    declared = _store(request).record(student).declaration(c)
    return _panel(
        request, student, c, _declaration_out(declared, request, student), refresh=True
    )


@router.post("/api/competencies/{competency}/declaration/check", tags=["rehearsal"])
def check_project_access(
    competency: str,
    sent: ProjectIn,
    request: Request,
    student: Student = Depends(current_student),
) -> fork_panel.Access:
    """Whether the Reading Day could read this project, before declaring it. Stores
    nothing."""
    _competency(request, competency, student)
    try:
        project = fork_panel.parse_project(sent.url)
    except NotAProject as error:
        raise HTTPException(422, str(error)) from error
    settings: Settings = request.app.state.settings
    return fork_panel.access(
        project, student.fork, request.app.state.access_check, settings.github_app_slug
    )


@router.post("/api/competencies/{competency}/declaration", tags=["rehearsal"])
def declare_evidence_project(
    competency: str,
    sent: DeclarationIn,
    request: Request,
    student: Student = Depends(current_student),
) -> ForkPanel:
    """Declare (or change) the Evidence Project of this Competency, until the Reading
    Day."""
    c = _competency(request, competency, student)
    declaration = _declaration_payload(request, student, sent)
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Project")
    entry = _store(request).save_declaration(student, c, declaration)
    return _panel(
        request,
        student,
        c,
        _declaration_out((entry.payload, entry.at), request, student),
        refresh=False,
    )


@router.delete("/api/competencies/{competency}/declaration", tags=["rehearsal"])
def withdraw_evidence_project(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> ForkPanel:
    """Withdraw the Evidence Project of this Competency: the Reading Day reads the fork
    again."""
    c = _competency(request, competency, student)
    _refuse_after_the_reading_day(request.app.state.settings, "your Evidence Project")
    store = _store(request)
    if store.record(student).declaration(c) is None:
        raise HTTPException(409, f"No Evidence Project is declared for {c}")
    store.save_declaration(student, c, {})
    return _panel(request, student, c, None, refresh=False)
