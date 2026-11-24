from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    field_validator,
)
from pydantic_core import ErrorDetails

from .competencies import competency_problems

SETTINGS_FILE = "course.toml"


class CompetencySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    minutes: PositiveInt


class LevelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class CourseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    competencies: dict[str, CompetencySettings] = {}
    levels: tuple[LevelSettings, ...]

    @field_validator("levels")
    @classmethod
    def _a_scale(cls, levels: tuple[LevelSettings, ...]) -> tuple[LevelSettings, ...]:
        if not levels:
            raise ValueError(
                "no Self-assessment level: list them in order, the last being the top"
            )
        ids = [level.id for level in levels]
        if len(set(ids)) != len(ids):
            raise ValueError("two Self-assessment levels share an id")
        return levels


def read_settings(folder: Path) -> tuple[CourseSettings | None, list[str]]:
    path = folder / SETTINGS_FILE
    if not path.is_file():
        return None, [f"{SETTINGS_FILE}: missing from the Course folder {folder}"]
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return None, [f"{SETTINGS_FILE}: not valid TOML ({error})"]
    try:
        settings = CourseSettings.model_validate(raw)
    except ValidationError as error:
        return None, [_problem(e) for e in error.errors()]
    problems = competency_problems(
        set(settings.competencies),
        lambda c: f"{SETTINGS_FILE}: no [competencies.{c}], so {c} has no title",
        lambda c: f"{SETTINGS_FILE}: [competencies.{c}] is no Competency of the Engine",
    )
    return (None, problems) if problems else (settings, [])


def _problem(error: ErrorDetails) -> str:
    where = ".".join(str(part) for part in error["loc"]) or "(root)"
    kind = error["type"]
    if kind == "missing":
        return f"{SETTINGS_FILE}: '{where}' is missing"
    if kind == "extra_forbidden":
        return f"{SETTINGS_FILE}: '{where}' is no setting of a Course"
    return f"{SETTINGS_FILE}: '{where}': {error['msg']}"
