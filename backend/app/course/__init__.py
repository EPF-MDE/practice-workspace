from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.content import COMPETENCIES, Competency, ContentError, load_content

from ._internal.settings_file import missing_and_unknown, read_settings

__all__ = ["CompetencyOfCourse", "Course", "Loading", "load_course", "router"]


@dataclass(frozen=True)
class CompetencyOfCourse:
    id: str
    title: str
    minutes: int
    content: Competency


@dataclass(frozen=True)
class Course:
    name: str
    competencies: dict[str, CompetencyOfCourse]


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
        content = load_content(folder)
    except ContentError as error:
        problems.append(str(error))
    else:
        missing, unknown = missing_and_unknown(set(content))
        problems += [
            f"{c.lower()}.md: missing, so {c} has no content" for c in missing
        ] + [f"content for {c}, which is no Competency of the Engine" for c in unknown]
    if settings is None or problems:
        return Loading(None, problems)
    competencies = {
        id: CompetencyOfCourse(
            id,
            settings.competencies[id].title,
            settings.competencies[id].minutes,
            content[id],
        )
        for id in COMPETENCIES
    }
    return Loading(Course(settings.name, competencies), [])


class CompetencyOut(BaseModel):
    id: str
    title: str
    minutes: int


class CourseOut(BaseModel):
    name: str
    competencies: list[CompetencyOut]


router = APIRouter()


@router.get("/api/course", tags=["course"])
def course(request: Request) -> CourseOut:
    loaded: Course = request.app.state.course
    return CourseOut(
        name=loaded.name,
        competencies=[
            CompetencyOut(id=c.id, title=c.title, minutes=c.minutes)
            for c in loaded.competencies.values()
        ],
    )
