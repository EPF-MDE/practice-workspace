from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import current_student
from app.closing import Level, Phase, Scale
from app.content import CompetencyContent, Image, load_content
from app.roster import Repository, Student

from ._internal.competencies import COMPETENCIES, competency_problems
from ._internal.settings_file import WhenNoneDeclared, read_settings

__all__ = [
    "COMPETENCIES",
    "Calendar",
    "Competency",
    "Course",
    "Group",
    "Loading",
    "WhenNoneDeclared",
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

    def phase(self, now: datetime) -> Phase:
        if now > self.reading_day_at:
            return "over"
        return "closed" if now > self.closes_at else "open"

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
    read_when_none_declared: WhenNoneDeclared
    images: dict[str, Image]

    @property
    def roster_names_evidence_projects(self) -> bool:
        return self.read_when_none_declared == WhenNoneDeclared.ROSTER


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
    content = load_content(
        folder,
        {name: group.block for name, group in groups.items()},
        to_get_there_levels=None if scale is None else scale.below_top,
    )
    problems += content.problems + competency_problems(
        content.with_a_file,
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
            content.competencies[id],
        )
        for id in COMPETENCIES
    }
    calendar = Calendar(
        settings.calendar.closes_at,
        settings.calendar.reading_day_at,
        settings.calendar.zone,
    )
    return Loading(
        Course(
            settings.name,
            groups,
            competencies,
            scale,
            calendar,
            settings.read_when_none_declared,
            content.images,
        ),
        [],
    )


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
    read_when_none_declared: WhenNoneDeclared


router = APIRouter()

AN_IMAGE_RUNS_NOTHING = "default-src 'none'; style-src 'unsafe-inline'; sandbox"


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
        read_when_none_declared=loaded.read_when_none_declared,
    )


@router.get(
    "/api/course/images/{name:path}",
    tags=["course"],
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
def image(
    name: str, request: Request, _: Student = Depends(current_student)
) -> Response:
    held = request.app.state.course.images.get(name)
    if held is None:
        raise HTTPException(404, "The Course folder holds no such image")
    return Response(
        held.data,
        media_type=held.media_type,
        headers={
            "Content-Security-Policy": AN_IMAGE_RUNS_NOTHING,
            "X-Content-Type-Options": "nosniff",
        },
    )
