from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app import evidence_panel
from app.evidence_panel import Declaration, NotAProject
from app.repository_reading import COMPETENCIES
from app.roster import Student
from app.settings import Settings
from app.store import StoredDeclaration

from .models import (
    MAX_URL_CHARS,
    MAX_WHAT_TO_READ_CHARS,
    DeclarationIn,
    _at_most,
)


def _changed(current: StoredDeclaration, new: dict[str, Any]) -> bool:
    return (current.url, current.what_to_read) != (
        new["url"],
        new["what_to_read"],
    )


def _declaration_payload(
    request: Request, student: Student, sent: DeclarationIn
) -> dict[str, Any]:
    _at_most(sent.url, MAX_URL_CHARS, "The project's URL")
    _at_most(sent.what_to_read, MAX_WHAT_TO_READ_CHARS, "Your note on what to read")
    try:
        project = evidence_panel.parse_project(sent.url)
    except NotAProject as error:
        raise HTTPException(422, str(error)) from error
    if not sent.what_to_read.strip():
        raise HTTPException(
            422,
            "Say in a note what to read in this project: a branch, a folder, a file",
        )
    settings: Settings = request.app.state.settings
    checked = evidence_panel.access(
        project,
        student.evidence_project,
        request.app.state.access_check,
        settings.github_app_slug,
    )
    return {
        "url": project.url,
        "what_to_read": sent.what_to_read.strip(),
        "repository": project.repository,
        "host": project.host,
        "access": checked.status,
    }


def _declared(
    declared: StoredDeclaration, request: Request, student: Student
) -> Declaration:
    project = evidence_panel.parse_project(declared.url)
    settings: Settings = request.app.state.settings
    return Declaration(
        url=project.url,
        what_to_read=declared.what_to_read,
        repository=project.repository,
        host=project.host,
        declares_roster_evidence_project=project.repository.lower()
        == student.evidence_project.lower(),
        declared_at=declared.at,
        access=evidence_panel.access(
            project,
            student.evidence_project,
            request.app.state.access_check,
            settings.github_app_slug,
        ),
    )


def _competency(request: Request, competency: str, student: Student) -> str:
    if competency not in COMPETENCIES:
        raise HTTPException(404, f"No Competency {competency}")
    return competency
