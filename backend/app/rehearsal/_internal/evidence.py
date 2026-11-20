"""The evidence panel and the Evidence Project, as the routes send them."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request

from app import evidence_panel
from app.evidence_panel import Declaration, EvidencePanel, NotAProject
from app.repository_reading import COMPETENCIES, StudentRepository
from app.roster import Student
from app.settings import Settings

from .models import (
    MAX_NOTE_CHARS,
    MAX_URL_CHARS,
    DeclarationIn,
    _at_most,
)

logger = logging.getLogger("app.rehearsal")


# --- The evidence panel and the Evidence Project ---------------------------------


def _repository(student: Student) -> StudentRepository:
    return StudentRepository(student.github_login, student.project, student.repository)


def _changed(current: dict[str, Any], new: dict[str, Any]) -> bool:
    return (current.get("url"), current.get("note")) != (new["url"], new["note"])


def _declaration_payload(
    request: Request, student: Student, sent: DeclarationIn
) -> dict[str, Any]:
    """A declaration as stored: the project, the note, and its access as checked when
    declared."""
    _at_most(sent.url, MAX_URL_CHARS, "The project's URL")
    _at_most(sent.note, MAX_NOTE_CHARS, "Your note on what to read")
    try:
        project = evidence_panel.parse_project(sent.url)
    except NotAProject as error:
        raise HTTPException(422, str(error)) from error
    if not sent.note.strip():
        raise HTTPException(
            422,
            "Say in a note what to read in this project: a branch, a folder, a file",
        )
    settings: Settings = request.app.state.settings
    checked = evidence_panel.access(
        project,
        student.repository,
        request.app.state.access_check,
        settings.github_app_slug,
    )
    return {
        "url": project.url,
        "note": sent.note.strip(),
        "repository": project.repository,
        "host": project.host,
        "access": checked.status,
    }


def _declaration_out(
    declared: tuple[dict[str, Any], datetime] | None, request: Request, student: Student
) -> Declaration | None:
    """The declaration with its access checked now (the App may have been installed
    since)."""
    if declared is None:
        return None
    payload, at = declared
    project = evidence_panel.parse_project(payload["url"])
    settings: Settings = request.app.state.settings
    return Declaration(
        url=project.url,
        note=payload.get("note", ""),
        repository=project.repository,
        host=project.host,
        is_default_repository=project.repository.lower() == student.repository.lower(),
        declared_at=at,
        access=evidence_panel.access(
            project,
            student.repository,
            request.app.state.access_check,
            settings.github_app_slug,
        ),
    )


def _panel(
    request: Request,
    student: Student,
    competency: str,
    declaration: Declaration | None,
    refresh: bool,
) -> EvidencePanel:
    source = request.app.state.repository_reading
    try:
        reading = (
            source.refresh(_repository(student))
            if refresh
            else source.read(_repository(student))
        )
    except Exception:  # the panel says so; the page and the closing step go on
        logger.exception("The repository of %s could not be read", student.github_login)
        return evidence_panel.unavailable_panel(
            competency, _repository(student), declaration
        )
    return evidence_panel.build_panel(competency, reading, declaration)


def _competency(request: Request, competency: str, student: Student) -> str:
    """A Competency of the course: its evidence panel and declaration exist before its
    content does."""
    if competency not in COMPETENCIES:
        raise HTTPException(404, f"No Competency {competency}")
    return competency
