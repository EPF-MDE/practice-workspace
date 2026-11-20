"""What the API sends and takes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

# --- What the API sends ------------------------------------------------------


class HtmlBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    html: str


class FieldBlock(BaseModel):
    type: Literal["field"] = "field"
    id: str
    kind: str  # "line", "text" or "choice"
    label_html: str
    options: list[str] | None = None  # a choice field's options, in order


class AnswerBlock(BaseModel):
    type: Literal["answer"] = "answer"
    locked: bool
    html: str | None  # None while locked


class CheckPointOut(BaseModel):
    id: str
    point: str  # the point of the review it is a hint for
    html: str


class PointBlock(BaseModel):
    type: Literal["point"] = "point"
    id: str
    band: str
    statement_html: str
    proof_html: str | None  # the proof sentence: what "I have done it" links to
    to_get_there_html: dict[str, str]
    missed_check_points: list[
        CheckPointOut
    ] = []  # the Student's ticks matching this point: a hint


class ExampleDrawingBlock(BaseModel):
    type: Literal["example-drawing"] = "example-drawing"
    snapshot: dict[str, Any]  # a tldraw snapshot, shown read-only
    caption_html: str


class CanvasBlock(BaseModel):
    type: Literal["canvas"] = "canvas"
    prompt_html: str


class ReferenceDrawingBlock(BaseModel):
    type: Literal["reference-drawing"] = "reference-drawing"
    locked: bool
    snapshot: dict[str, Any] | None  # None while locked
    caption_html: str | None
    check_points: list[CheckPointOut] | None


class WaitingBlock(BaseModel):
    type: Literal["waiting"] = "waiting"
    step: str  # the earlier step whose answer this step waits for
    html: str  # what to send first


class WaitsFor(BaseModel):
    step: str
    title: str


class DrawingSent(BaseModel):
    version: int
    sent_at: datetime
    png_bytes: int
    snapshot_bytes: int


class SentVersion(BaseModel):
    fields: dict[str, str]
    version: int
    sent_at: datetime


class Sent(SentVersion):
    history: list[SentVersion]  # every version, oldest first, the current one last


class Question(BaseModel):
    text: str
    asked_at: datetime


class StepOut(BaseModel):
    id: str
    title: str
    minutes: int
    kind: str
    fills: str | None
    optional: bool  # the one optional redraw: nothing depends on it
    blocks: list[
        HtmlBlock
        | FieldBlock
        | AnswerBlock
        | PointBlock
        | ExampleDrawingBlock
        | CanvasBlock
        | ReferenceDrawingBlock
        | WaitingBlock
    ]
    # Until the earlier step's answer is stored: its Group blocks and fields are
    # withheld.
    waits_for: WaitsFor | None
    sent: Sent | None
    drawing: DrawingSent | None  # a drawing step: the Student's drawing, once sent
    missed_check_points: (
        list[str] | None
    )  # the check points the Student ticked as missed, once ticked
    questions: list[Question]


class PointLevel(BaseModel):
    level: str  # "not-yet", "understand", "redo", "done"
    link: str | None  # for "done" only: the Student's work on GitHub or GitLab


class PointLevelNow(PointLevel):
    since: datetime  # when the point took this level and link


class SelfAssessmentVersion(BaseModel):
    levels: dict[str, PointLevel]
    version: int
    sent_at: datetime


class SelfAssessment(BaseModel):
    levels: dict[str, PointLevelNow]  # per point id, the points rated only
    version: int
    sent_at: datetime
    history: list[SelfAssessmentVersion]  # every version, oldest first


class EvidencePlanVersion(BaseModel):
    text: str  # the text sent: the Student's own, or the draft they confirmed untouched
    # the untouched draft: not yet the Student's text, so the page keeps drafting from
    # the levels
    drafted: bool
    example: str | None  # the example for the Eval, once the closing step is sent
    confirmed: bool  # the closing step confirmed it
    version: int
    sent_at: datetime


class EvidencePlan(EvidencePlanVersion):
    history: list[EvidencePlanVersion]


class CompetencyPage(BaseModel):
    competency: str
    title: str
    intro_html: str
    steps: list[StepOut]
    closes_at: datetime
    closed: bool  # after it, a level already given only moves up to "I have done it"
    reading_day_at: datetime
    reading_day_passed: bool  # after it, nothing changes
    self_assessment: SelfAssessment | None
    evidence_plan: (
        EvidencePlan | None
    )  # the Student's text: once sent, it wins over the draft
    evidence_plan_draft: (
        str  # drafted from the levels stored, the Transfer, the Evidence Project
    )
    evidence_project: (
        str | None
    )  # the declared Evidence Project's URL: the Transfer's default project
    tldraw_license_key: str  # empty locally: tldraw needs none in development


class AnswerIn(BaseModel):
    fields: dict[str, str]


class AnswerSent(BaseModel):
    version: int
    sent_at: datetime
    unlocked: list[str]  # the html of each answer block this send releases


class QuestionIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


# The longest text each field takes. With them, the largest send (the closing step:
# plan, example, declaration and an evidence panel snapshot of at most 40,000
# characters) fits one GitHub comment; a send the Store still finds too large
# (escapes counted) gets a 422 too, from app.main.
MAX_FIELD_CHARS = 4_000  # one field of an answer
MAX_PLAN_CHARS = 12_000  # the Evidence Plan: a full draft is about 7,000
MAX_EXAMPLE_CHARS = 2_000  # the example for the Eval
MAX_NOTE_CHARS = 2_000  # what to read in an Evidence Project
MAX_URL_CHARS = 500  # an Evidence Project's URL, a "done" link


def _at_most(text: str | None, limit: int, what: str) -> None:
    """Refuse a text over its limit with a sentence the page shows as it is."""
    if text is not None and len(text) > limit:
        raise HTTPException(
            422,
            f"{what} is too long: at most {limit:,} characters, it has {len(text):,}",
        )


MAX_PNG_BYTES = 5_000_000
MAX_SNAPSHOT_BYTES = 2_000_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class DrawingIn(BaseModel):
    png_base64: str  # the PNG tldraw exported in the browser
    snapshot: dict[str, Any]  # tldraw's getSnapshot(editor.store): {document, session}


class DrawingStored(DrawingSent):
    reference: ReferenceDrawingBlock | None  # released by this send
    unlocked: list[str]  # the html of each answer block this send releases


class MyDrawing(BaseModel):
    version: int
    sent_at: datetime
    snapshot: dict[str, Any]


class CheckPointsIn(BaseModel):
    missed: list[str]


class CheckPointsSent(BaseModel):
    missed: list[str]
    version: int
    sent_at: datetime


class SelfAssessmentIn(BaseModel):
    levels: dict[str, PointLevel]
    # The ticks this browser kept since the drawing was sent, per drawing step: they
    # ride with this send.
    missed_check_points: dict[str, list[str]] | None = None


class Stored(BaseModel):
    version: int
    sent_at: datetime


class LevelsIn(BaseModel):
    levels: dict[str, PointLevel]


class Draft(BaseModel):
    text: str


class EvidencePlanIn(BaseModel):
    text: str  # at most MAX_PLAN_CHARS
    drafted: bool = (
        False  # the text is the draft, untouched: only an edit makes it the Student's
    )


class DeclarationIn(BaseModel):
    url: str  # a repository on GitHub or GitLab, at most MAX_URL_CHARS
    note: str  # what to read, at most MAX_NOTE_CHARS


class ProjectIn(BaseModel):
    url: str = Field(max_length=500)


class ClosingIn(BaseModel):
    text: str  # the Evidence Plan as confirmed, at most MAX_PLAN_CHARS
    example: str  # one example for the Eval, at most MAX_EXAMPLE_CHARS
    drafted: bool = (
        False  # the text is the draft, untouched: only an edit makes it the Student's
    )
    # An Evidence Project declared in the closing step: it rides with this send.
    declaration: DeclarationIn | None = None
