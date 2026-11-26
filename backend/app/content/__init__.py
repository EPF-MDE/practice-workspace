from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._internal.images import IMAGES_URL, Image, read_images
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
    "IMAGES_URL",
    "Answer",
    "Block",
    "Canvas",
    "CheckPoint",
    "CompetencyContent",
    "ContentError",
    "ContentLoading",
    "ExampleDrawing",
    "Field",
    "Html",
    "Image",
    "Page",
    "Point",
    "ReferenceDrawing",
    "Step",
    "Waiting",
    "load_content",
    "parse_competency",
]


@dataclass(frozen=True)
class ContentLoading:
    competencies: dict[str, CompetencyContent]
    with_a_file: set[str]
    images: dict[str, Image]
    problems: list[str]


def load_content(
    directory: str | Path,
    group_block_ids: Mapping[str, str],
    *,
    to_get_there_levels: Collection[str] | None,
) -> ContentLoading:
    directory = Path(directory).resolve()

    def drawings(src: str) -> dict[str, Any]:
        path = (directory / src).resolve()
        if not path.is_relative_to(directory):
            raise ContentError(f"the drawing '{src}' is outside the Course folder")
        if not path.is_file():
            raise ContentError("the Course folder holds no such file")
        snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return snapshot

    held = read_images(directory)
    loading = ContentLoading({}, set(), {}, [])
    for path in sorted(directory.glob("c[0-9].md")):
        try:
            competency = parse_competency(
                path.read_text(encoding="utf-8"),
                group_block_ids,
                path.name,
                drawings,
                to_get_there_levels=to_get_there_levels,
                images=held,
            )
        except ContentError as error:
            loading.with_a_file.add(path.stem.upper())
            loading.problems.extend(error.problems)
            continue
        if path.name != f"{competency.id.lower()}.md":
            loading.problems.append(
                f"{path.name}: holds the content of {competency.id}, "
                f"which belongs in {competency.id.lower()}.md"
            )
            continue
        loading.with_a_file.add(competency.id)
        loading.competencies[competency.id] = competency
    for competency in loading.competencies.values():
        loading.images.update(
            (name, held[name]) for name in competency.images_shown if name in held
        )
    return loading
