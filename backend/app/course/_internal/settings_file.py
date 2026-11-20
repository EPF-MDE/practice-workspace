from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import ErrorDetails

SETTINGS_FILE = "course.toml"


class CourseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)


def read_settings(folder: Path) -> tuple[CourseSettings | None, list[str]]:
    path = folder / SETTINGS_FILE
    if not path.is_file():
        return None, [f"{SETTINGS_FILE}: missing from the Course folder {folder}"]
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return None, [f"{SETTINGS_FILE}: not valid TOML ({error})"]
    try:
        return CourseSettings.model_validate(raw), []
    except ValidationError as error:
        return None, [_problem(e) for e in error.errors()]


def _problem(error: ErrorDetails) -> str:
    where = ".".join(str(part) for part in error["loc"]) or "(root)"
    kind = error["type"]
    if kind == "missing":
        return f"{SETTINGS_FILE}: '{where}' is missing"
    if kind == "extra_forbidden":
        return f"{SETTINGS_FILE}: '{where}' is no setting of a Course"
    return f"{SETTINGS_FILE}: '{where}': {error['msg']}"
