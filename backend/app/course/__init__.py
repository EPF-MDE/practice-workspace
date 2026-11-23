from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.closing import Level, Scale
from app.content import CompetencyContent, ContentError, load_content
from app.roster import Repository

from ._internal.competencies import COMPETENCIES, competency_problems
from ._internal.settings_file import read_settings

__all__ = [
    "COMPETENCIES",
    "Calendar",
    "Competency",
    "Course",
    "Group",
    "Loading",
    "load_course",
    "router",
]


@dataclass(frozen=True)
class Competency:
    id: str
    title: str
    minutes: int
    content: CompetencyContent


@dataclass(frozen=True)
class Group:
    name: str
    block: str
    upstream: Repository | None


@dataclass(frozen=True)
class Calendar:
    closes_at: datetime
    reading_day_at: datetime
    time_zone: ZoneInfo

    def in_course_time(self, instant: datetime) -> str:
        when = instant.astimezone(self.time_zone).strftime("%-d %B %Y at %H:%M")
        return f"{when}, {self.time_zone.key} time"


@dataclass(frozen=True)
class Course:
    name: str
    groups: dict[str, Group]
    competencies: dict[str, Competency]
    scale: Scale
    calendar: Calendar


@dataclass(frozen=True)
class Loading:
    course: Course | None
    problems: list[str]


def load_course(folder: str | Path) -> Loading:
    folder = Path(folder)
    if not folder.is_dir():
        return Loading(None, [f"{folder}: no such Course folder"])
    settings, problems = read_settings(folder)
    scale = (
        None
        if settings is None
        else Scale(tuple(Level(level.id, level.label) for level in settings.levels))
    )
    groups = {
        group.name: Group(
            group.name,
            group.block,
            Repository(group.upstream) if group.upstream else None,
        )
        for group in (settings.groups if settings else ())
    }
    try:
        content = load_content(
            folder,
            {name: group.block for name, group in groups.items()},
            to_get_there_levels=None if scale is None else scale.below_top,
        )
    except ContentError as error:
        problems.append(str(error))
    else:
        problems += competency_problems(
            set(content),
            lambda c: f"{c.lower()}.md: missing, so {c} has no content",
            lambda c: f"content for {c}, which is no Competency of the Engine",
        )
    if settings is None or scale is None or problems:
        return Loading(None, problems)
    competencies = {
        id: Competency(
            id,
            settings.competencies[id].title,
            settings.competencies[id].minutes,
            content[id],
        )
        for id in COMPETENCIES
    }
    calendar = Calendar(
        settings.calendar.closes_at,
        settings.calendar.reading_day_at,
        settings.calendar.zone,
    )
    return Loading(Course(settings.name, groups, competencies, scale, calendar), [])


class LevelOut(BaseModel):
    id: str
    label: str


class CompetencyOut(BaseModel):
    id: str
    title: str
    minutes: int


class CourseOut(BaseModel):
    name: str
    competencies: list[CompetencyOut]
    scale: list[LevelOut]


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
        scale=[
            LevelOut(id=level.id, label=level.label) for level in loaded.scale.levels
        ],
    )
