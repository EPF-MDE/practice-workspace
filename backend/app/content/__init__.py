from __future__ import annotations

import json
from collections.abc import Collection
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
from ._internal.render import CompetencyContent

__all__ = [
    "Answer",
    "Block",
    "Canvas",
    "CheckPoint",
    "CompetencyContent",
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


def load_content(
    directory: str | Path, to_get_there_levels: Collection[str] | None = None
) -> dict[str, CompetencyContent]:
    directory = Path(directory).resolve()

    def drawings(src: str) -> dict[str, Any]:
        path = (directory / src).resolve()
        if not path.is_relative_to(directory):
            raise ContentError(f"the drawing '{src}' is outside the content folder")
        snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return snapshot

    content: dict[str, CompetencyContent] = {}
    for path in sorted(directory.glob("c[0-9].md")):
        competency = parse_competency(
            path.read_text(encoding="utf-8"), path.name, drawings, to_get_there_levels
        )
        if path.name != f"{competency.id.lower()}.md":
            raise ContentError(
                f"{path.name}: holds the content of {competency.id}, "
                f"which belongs in {competency.id.lower()}.md"
            )
        content[competency.id] = competency
    return content
