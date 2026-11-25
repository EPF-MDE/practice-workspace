from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FIELD_KINDS = ("line", "text", "choice")
BANDS = ("Basic", "Solid", "Outstanding")
DRAWING_DIRECTIVES = {"example-drawing", "canvas", "reference-drawing", "check-point"}
DIRECTIVES = {
    "field",
    "answer",
    "point",
    "proof",
    "to-get-there",
    "instructor",
    "waiting",
    *DRAWING_DIRECTIVES,
}
CHECK_POINTS = range(3, 6)
STEP_KINDS = (
    "read",
    "answer",
    "drawing",
    "transfer",
    "closing",
)

INSTRUCTOR_MARKERS = (
    "--instructor",
    "banding anchor",
    "deepening",
    "questionnaire",
    "project brief",
    "seeded fault",
    "course gateway",
    "it manager",
)
UNVALIDATED_MARKER = "TO VALIDATE"


def _options(attrs: dict[str, str]) -> tuple[str, ...]:
    return tuple(o.strip() for o in attrs.get("options", "").split("|") if o.strip())


class ContentError(ValueError):
    def __init__(self, *problems: str) -> None:
        super().__init__("\n".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class Html:
    html: str


@dataclass(frozen=True)
class Field:
    id: str
    kind: str
    label_html: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Answer:
    html: str


@dataclass(frozen=True)
class Point:
    id: str
    band: str
    statement_html: str
    proof_html: str | None
    to_get_there_html: dict[str, str]


@dataclass(frozen=True)
class ExampleDrawing:
    snapshot: dict[str, Any]
    caption_html: str


@dataclass(frozen=True)
class Canvas:
    prompt_html: str


@dataclass(frozen=True)
class CheckPoint:
    id: str
    point: str
    html: str


@dataclass(frozen=True)
class ReferenceDrawing:
    snapshot: dict[str, Any]
    caption_html: str
    check_points: tuple[CheckPoint, ...]


@dataclass(frozen=True)
class Waiting:
    html: str


Block = (
    Html | Field | Answer | Point | ExampleDrawing | Canvas | ReferenceDrawing | Waiting
)


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    minutes: int
    kind: str
    fills: str | None
    blocks: tuple[Block, ...]
    optional: bool = False
    after: str | None = None
    waiting: tuple[Block, ...] = ()

    @property
    def fields(self) -> list[Field]:
        return [b for b in self.blocks if isinstance(b, Field)]

    @property
    def reference(self) -> ReferenceDrawing | None:
        return next((b for b in self.blocks if isinstance(b, ReferenceDrawing)), None)


@dataclass(frozen=True)
class Page:
    competency: str
    intro_html: str
    steps: tuple[Step, ...]

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)
