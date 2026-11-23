from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError


class HtmlBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    html: str


class FieldBlock(BaseModel):
    type: Literal["field"] = "field"
    id: str
    kind: str
    label_html: str
    options: list[str] | None = None


class AnswerBlock(BaseModel):
    type: Literal["answer"] = "answer"
    locked: bool
    html: str | None


class CheckPointOut(BaseModel):
    id: str
    point: str
    html: str


class PointBlock(BaseModel):
    type: Literal["point"] = "point"
    id: str
    band: str
    statement_html: str
    proof_html: str | None
    to_get_there_html: dict[str, str]
    missed_check_points: list[CheckPointOut] = []


class ExampleDrawingBlock(BaseModel):
    type: Literal["example-drawing"] = "example-drawing"
    snapshot: dict[str, Any]
    caption_html: str


class CanvasBlock(BaseModel):
    type: Literal["canvas"] = "canvas"
    prompt_html: str


class ReferenceDrawingBlock(BaseModel):
    type: Literal["reference-drawing"] = "reference-drawing"
    locked: bool
    snapshot: dict[str, Any] | None
    caption_html: str | None
    check_points: list[CheckPointOut] | None


class WaitingBlock(BaseModel):
    type: Literal["waiting"] = "waiting"
    step: str
    html: str


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
    history: list[SentVersion]


class Question(BaseModel):
    text: str
    asked_at: datetime


class StepOut(BaseModel):
    id: str
    title: str
    minutes: int
    kind: str
    fills: str | None
    optional: bool
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
    waits_for: WaitsFor | None
    sent: Sent | None
    drawing: DrawingSent | None
    missed_check_points: list[str] | None
    questions: list[Question]


class PointLevel(BaseModel):
    level: str
    link: str | None


class PointLevelNow(PointLevel):
    since: datetime


class SelfAssessmentVersion(BaseModel):
    levels: dict[str, PointLevel]
    version: int
    sent_at: datetime


class SelfAssessment(BaseModel):
    levels: dict[str, PointLevelNow]
    version: int
    sent_at: datetime
    history: list[SelfAssessmentVersion]


class EvidencePlanVersion(BaseModel):
    text: str
    drafted: bool
    example: str | None
    confirmed: bool
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
    closed: bool
    reading_day_at: datetime
    reading_day_passed: bool
    self_assessment: SelfAssessment | None
    evidence_plan: EvidencePlan | None
    evidence_plan_draft: str
    evidence_project: str | None
    tldraw_license_key: str


MAX_FIELD_CHARS = 4_000
MAX_QUESTION_CHARS = 4_000
MAX_PLAN_CHARS = 12_000
MAX_EXAMPLE_CHARS = 2_000
MAX_NOTE_CHARS = 2_000
MAX_URL_CHARS = 500

TOO_LONG = "too_long"


def _refuse_over(text: str | None, limit: int, what: str) -> None:
    if text is not None and len(text) > limit:
        raise PydanticCustomError(
            TOO_LONG,
            "{what} is too long: at most {limit} characters, it has {length}",
            {"what": what, "limit": f"{limit:,}", "length": f"{len(text):,}"},
        )


def _at_most(limit: int, what: str) -> AfterValidator:
    def check(text: str) -> str:
        _refuse_over(text, limit, what)
        return text

    return AfterValidator(check)


def _each_at_most[V](
    limit: int, what: str, text: Callable[[V], str | None]
) -> AfterValidator:
    def check(values: dict[str, V]) -> dict[str, V]:
        for key, value in values.items():
            _refuse_over(text(value), limit, what.format(key=key))
        return values

    return AfterValidator(check)


QuestionText = Annotated[
    str, Field(min_length=1), _at_most(MAX_QUESTION_CHARS, "Your question")
]
PlanText = Annotated[str, _at_most(MAX_PLAN_CHARS, "Your Evidence Plan")]
ExampleText = Annotated[str, _at_most(MAX_EXAMPLE_CHARS, "Your example for the Eval")]
NoteText = Annotated[str, _at_most(MAX_NOTE_CHARS, "Your note on what to read")]
EvidenceProjectUrl = Annotated[
    str, _at_most(MAX_URL_CHARS, "The Evidence Project's URL")
]
AnswerFields = Annotated[
    dict[str, str],
    _each_at_most(MAX_FIELD_CHARS, "Your answer in '{key}'", lambda text: text),
]
PointLevels = Annotated[
    dict[str, PointLevel],
    _each_at_most(MAX_URL_CHARS, "The link for {key}", lambda level: level.link),
]


class AnswerIn(BaseModel):
    fields: AnswerFields


class AnswerSent(BaseModel):
    version: int
    sent_at: datetime
    unlocked: list[str]


class QuestionIn(BaseModel):
    text: QuestionText


MAX_PNG_BYTES = 5_000_000
MAX_SNAPSHOT_BYTES = 2_000_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class DrawingIn(BaseModel):
    png_base64: str
    snapshot: dict[str, Any]


class DrawingStored(DrawingSent):
    reference: ReferenceDrawingBlock | None
    unlocked: list[str]


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
    levels: PointLevels
    missed_check_points: dict[str, list[str]] | None = None


class Stored(BaseModel):
    version: int
    sent_at: datetime


class LevelsIn(BaseModel):
    levels: PointLevels


class Draft(BaseModel):
    text: str


class EvidencePlanIn(BaseModel):
    text: PlanText
    drafted: bool = False


class DeclarationIn(BaseModel):
    url: EvidenceProjectUrl
    note: NoteText


class ProjectIn(BaseModel):
    url: EvidenceProjectUrl


class ClosingIn(BaseModel):
    text: PlanText
    example: ExampleText
    drafted: bool = False
    declaration: DeclarationIn | None = None
