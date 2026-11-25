from __future__ import annotations

import tomllib
from collections import Counter
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
BLOCK_ID = r"^[A-Za-z][\w-]*$"
REPOSITORY = r"^[\w.-]+/[\w.-]+$"


class GroupSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    block: str = Field(pattern=BLOCK_ID)
    upstream: str | None = Field(default=None, pattern=REPOSITORY)


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
    groups: tuple[GroupSettings, ...] = Field(min_length=1)
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
    problems = _duplicates(settings) + competency_problems(
        set(settings.competencies),
        lambda c: f"{SETTINGS_FILE}: no [competencies.{c}], so {c} has no title",
        lambda c: f"{SETTINGS_FILE}: [competencies.{c}] is no Competency of the Engine",
    )
    return (None, problems) if problems else (settings, [])


def _duplicates(settings: CourseSettings) -> list[str]:
    problems = []
    for key in ("name", "block"):
        counts = Counter(getattr(group, key) for group in settings.groups)
        problems += [
            f"{SETTINGS_FILE}: two Groups share the {key} '{value}'"
            for value, count in counts.items()
            if count > 1
        ]
    return problems


def _problem(error: ErrorDetails) -> str:
    where = ".".join(str(part) for part in error["loc"]) or "(root)"
    kind = error["type"]
    if kind == "missing":
        return f"{SETTINGS_FILE}: '{where}' is missing"
    if kind == "extra_forbidden":
        return f"{SETTINGS_FILE}: '{where}' is no setting of a Course"
    return f"{SETTINGS_FILE}: '{where}': {error['msg']}"
