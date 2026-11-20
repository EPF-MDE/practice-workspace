from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._internal.model import (
    Answer,
    Block,
    Canvas,
    CheckPoint,
    ContentError,
    ExampleDrawing,
    Field,
    Html,
    Page,
    Point,
    ReferenceDrawing,
    Step,
    Waiting,
)
from ._internal.parse import parse_competency
from ._internal.render import Competency

__all__ = [
    "Answer",
    "Block",
    "Canvas",
    "CheckPoint",
    "Competency",
    "ContentError",
    "ExampleDrawing",
    "Field",
    "Html",
    "Page",
    "Point",
    "ReferenceDrawing",
    "Step",
    "Waiting",
    "load_content",
    "parse_competency",
]


def load_content(directory: str | Path) -> dict[str, Competency]:
    directory = Path(directory).resolve()

    def drawings(src: str) -> dict[str, Any]:
        path = (directory / src).resolve()
        if not path.is_relative_to(directory):
            raise ContentError(f"the drawing '{src}' is outside the content folder")
        snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return snapshot

    content: dict[str, Competency] = {}
    for path in sorted(directory.glob("c[0-9].md")):
        competency = parse_competency(
            path.read_text(encoding="utf-8"), path.name, drawings
        )
        content[competency.id] = competency
    return content
