"""The course content: one Markdown file per Competency, read once at start.

The format (the Instructor writes and reviews it like a Student document):

    ---
    competency: C1
    title: Design a resilient web architecture under non-functional constraints
    ---

    Intro, above the first step.

    ## Guided calculation {#guided-calculation minutes=10}

    ::: oceens
    Only an OcéENS Student receives this.

    ::: field {#sentence kind=line}
    The field's label: **___ is at most ___**
    :::

    ::: answer
    Withheld until the Student's own answer to this step is stored.
    :::
    :::

- A step is a level-2 heading with attributes: `{#id minutes=n [kind=k] [fills=point]}`.
- Directives are pandoc-style fenced divs, nested: `oceens`, `mathutrice` (Group
  blocks), `field {#id kind=line|text}` (or `kind=choice options="a|b|c"`: one option to
  pick, #470), `answer`, `point {#C1.a band=...}` with `proof` and `to-get-there
  {level=not-yet|understand|redo}` inside, and `instructor` (authoring notes, stripped
  like HTML comments).
- A drawing step (`kind=drawing`, #465) holds `example-drawing {src=...}`
  (a read-only canvas shown at once, its body the caption), one `canvas`
  per Group (its body the prompt: only the drawing's start and end points),
  and `reference-drawing {src=...}` (withheld until the Student's drawing is
  sent) with 3 to 5 `check-point {#id point=C1.c}` inside. `src` is a tldraw
  snapshot (JSON) in the content folder. One drawing step per Competency may
  be `optional=yes`: nothing depends on it.
- A Transfer (`kind=transfer fills=C1.b`, #466) has a field `#project` (empty: the
  Evidence Project); its answer fills that point's "To get there" in the Practice
  Plan. The closing step (`kind=closing`) holds the review's points, each with at
  most one `proof` sentence (it completes "At the Eval, I will show ...").
- A step may wait for an earlier step's answer (`after=observe-and-rank`):
  until it is stored, the Student receives only the step's shared Markdown
  (the Worked Example part) and a marker, never its Group blocks or fields.
  The marker is the step's `::: waiting` block (shared, outside the Group
  blocks), or a sentence naming the earlier step.
- Loading refuses anything that could serve what it must not: an unknown
  directive, an unclosed block, an answer in a step without fields, a step
  with one Group block but not the other, an Instructor-Material marker.

`Competency.for_group(group)` is what one Group's Students may be sent, answer
blocks included: withholding them until the answer is stored is the caller's
job, through `Answer` blocks it can recognise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._model import (
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
from ._parse import parse_competency
from ._render import Competency

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
    """Every `c<n>.md` in a folder, by Competency id ("C1")."""
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
