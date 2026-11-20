"""The fork panel and the Evidence Project, as the routes send them."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request

from app import fork_panel
from app.fork_panel import Declaration, ForkPanel, NotAProject
from app.fork_reading import COMPETENCIES, StudentFork
from app.roster import Student
from app.settings import Settings

from .models import (
    MAX_NOTE_CHARS,
    MAX_URL_CHARS,
    DeclarationIn,
    _at_most,
)

logger = logging.getLogger("app.rehearsal")


# --- The fork panel and the Evidence Project ---------------------------------


def _fork(student: Student) -> StudentFork:
    return StudentFork(student.github_login, student.project, student.fork)


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
        project = fork_panel.parse_project(sent.url)
    except NotAProject as error:
        raise HTTPException(422, str(error)) from error
    if not sent.note.strip():
        raise HTTPException(
            422,
            "Say in a note what to read in this project: a branch, a folder, a file",
        )
    settings: Settings = request.app.state.settings
    checked = fork_panel.access(
        project, student.fork, request.app.state.access_check, settings.github_app_slug
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
    project = fork_panel.parse_project(payload["url"])
    settings: Settings = request.app.state.settings
    return Declaration(
        url=project.url,
        note=payload.get("note", ""),
        repository=project.repository,
        host=project.host,
        is_fork=project.repository.lower() == student.fork.lower(),
        declared_at=at,
        access=fork_panel.access(
            project,
            student.fork,
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
) -> ForkPanel:
    source = request.app.state.fork_reading
    try:
        reading = (
            source.refresh(_fork(student)) if refresh else source.read(_fork(student))
        )
    except Exception:  # the panel says so; the page and the closing step go on
        logger.exception("The fork of %s could not be read", student.github_login)
        return fork_panel.unavailable_panel(competency, _fork(student), declaration)
    return fork_panel.build_panel(competency, reading, declaration)


def _competency(request: Request, competency: str, student: Student) -> str:
    """A Competency of the course: its fork panel and declaration exist before its
    content does."""
    if competency not in COMPETENCIES:
        raise HTTPException(404, f"No Competency {competency}")
    return competency
