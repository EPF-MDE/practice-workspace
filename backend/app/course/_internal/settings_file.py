from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError
from pydantic_core import ErrorDetails

from app.content import COMPETENCIES

SETTINGS_FILE = "course.toml"


class CompetencySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    minutes: PositiveInt


class CourseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    competencies: dict[str, CompetencySettings]


def competency_problems(
    ids: set[str], missing: Callable[[str], str], unknown: Callable[[str], str]
) -> list[str]:
    return [missing(c) for c in COMPETENCIES if c not in ids] + [
        unknown(c) for c in sorted(ids - set(COMPETENCIES))
    ]


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
