"""The format's vocabulary, and what a Student may be sent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import roster

# Each Group's name (the roster's) -> its content block's directive.
GROUPS = {name: group.directive for name, group in roster.GROUPS.items()}
FIELD_KINDS = ("line", "text", "choice")
BANDS = ("Basic", "Solid", "Outstanding")
LEVELS_BELOW_DONE = ("not-yet", "understand", "redo")
DRAWING_DIRECTIVES = {"example-drawing", "canvas", "reference-drawing", "check-point"}
DIRECTIVES = {
    *GROUPS.values(),
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
# A step's kind: "read" or "answer" by default; "drawing" a redraw (#465); "transfer"
# fills its point's "To get there" from the Student's answer, and "closing" holds the
# review's points (#466).
STEP_KINDS = (
    "read",
    "answer",
    "drawing",
    "transfer",
    "closing",
)  # a Reference Drawing has 3 to 5 check points

# Words that only Instructor Material uses: none may reach a Student.
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
# A figure the Instructor has not validated yet: kept in an HTML comment, never served,
# even in an answer.
UNVALIDATED_MARKER = "TO VALIDATE"


def _options(attrs: dict[str, str]) -> tuple[str, ...]:
    """A choice field's `options="a|b|c"`, in order."""
    return tuple(o.strip() for o in attrs.get("options", "").split("|") if o.strip())


class ContentError(ValueError):
    """A content file the app refuses to serve."""


# --- What a Student may be sent ----------------------------------------------


@dataclass(frozen=True)
class Html:
    html: str


@dataclass(frozen=True)
class Field:
    id: str
    kind: str  # "line", "text", or "choice" (one of `options`)
    label_html: str
    options: tuple[str, ...] = ()  # a choice field's options, in order


@dataclass(frozen=True)
class Answer:
    html: str


@dataclass(frozen=True)
class Point:
    id: str  # "C1.a"
    band: str  # "Basic", "Solid", "Outstanding"
    statement_html: str
    proof_html: str | None
    to_get_there_html: dict[str, str]  # level ("not-yet", "understand", "redo") -> html


@dataclass(frozen=True)
class ExampleDrawing:
    """A drawing of a simpler system, shown read-only before the Student redraws."""

    snapshot: dict[str, Any]  # a tldraw snapshot
    caption_html: str


@dataclass(frozen=True)
class Canvas:
    """Where the Student redraws; the prompt gives only the drawing's start and end
    points."""

    prompt_html: str


@dataclass(frozen=True)
class CheckPoint:
    id: str
    point: str  # the point of the review it is a hint for ("C1.c")
    html: str


@dataclass(frozen=True)
class ReferenceDrawing:
    """The Instructor's drawing: withheld, like an answer, until the Student's drawing
    is sent."""

    snapshot: dict[str, Any]
    caption_html: str
    check_points: tuple[CheckPoint, ...]


@dataclass(frozen=True)
class Waiting:
    """Where a step waiting for an earlier step's answer says so, in place of what it
    withholds."""

    html: str


Block = (
    Html | Field | Answer | Point | ExampleDrawing | Canvas | ReferenceDrawing | Waiting
)


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    minutes: int
    # "read", "answer", "drawing", or what a later ticket declares ("closing"...)
    kind: str
    fills: str | None  # a Transfer's point
    blocks: tuple[Block, ...]
    optional: bool = False  # the one redraw per Competency that nothing depends on
    after: str | None = None  # the earlier step whose answer this one waits for
    # What a waiting step serves until that answer is stored: its shared Markdown and a
    # Waiting marker.
    waiting: tuple[Block, ...] = ()

    @property
    def fields(self) -> list[Field]:
        return [b for b in self.blocks if isinstance(b, Field)]

    @property
    def reference(self) -> ReferenceDrawing | None:
        return next((b for b in self.blocks if isinstance(b, ReferenceDrawing)), None)


@dataclass(frozen=True)
class Page:
    """A Competency as one Group's Students see it, answers not yet withheld."""

    competency: str
    title: str
    intro_html: str
    steps: tuple[Step, ...]

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)
