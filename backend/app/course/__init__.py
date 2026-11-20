from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.content import Competency, ContentError, load_content

from ._internal.settings_file import SETTINGS_FILE, read_settings

__all__ = ["SETTINGS_FILE", "Course", "Loading", "load_course", "router"]


@dataclass(frozen=True)
class Course:
    name: str
    competencies: dict[str, Competency]


@dataclass(frozen=True)
class Loading:
    course: Course | None
    problems: list[str]


def load_course(folder: str | Path) -> Loading:
    folder = Path(folder)
    if not folder.is_dir():
        return Loading(None, [f"{folder}: no such Course folder"])
    settings, problems = read_settings(folder)
    try:
        competencies = load_content(folder)
    except ContentError as error:
        problems.append(str(error))
        competencies = {}
    if settings is None or problems:
        return Loading(None, problems)
    return Loading(Course(settings.name, competencies), [])


class CourseOut(BaseModel):
    name: str


router = APIRouter()


@router.get("/api/course", tags=["course"])
def course(request: Request) -> CourseOut:
    loaded: Course = request.app.state.course
    return CourseOut(name=loaded.name)
