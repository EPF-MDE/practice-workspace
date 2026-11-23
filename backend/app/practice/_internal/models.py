from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field


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


class AnswerIn(BaseModel):
    fields: dict[str, str]


class AnswerSent(BaseModel):
    version: int
    sent_at: datetime
    unlocked: list[str]


class QuestionIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


MAX_FIELD_CHARS = 4_000
MAX_PLAN_CHARS = 12_000
MAX_EXAMPLE_CHARS = 2_000
MAX_WHAT_TO_READ_CHARS = 2_000
MAX_URL_CHARS = 500


def _at_most(text: str | None, limit: int, what: str) -> None:
    if text is not None and len(text) > limit:
        raise HTTPException(
            422,
            f"{what} is too long: at most {limit:,} characters, it has {len(text):,}",
        )


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
    levels: dict[str, PointLevel]
    missed_check_points: dict[str, list[str]] | None = None


class Stored(BaseModel):
    version: int
    sent_at: datetime


class LevelsIn(BaseModel):
    levels: dict[str, PointLevel]


class Draft(BaseModel):
    text: str


class EvidencePlanIn(BaseModel):
    text: str
    drafted: bool = False


class DeclarationIn(BaseModel):
    url: str
    what_to_read: str


class ProjectIn(BaseModel):
    url: str = Field(max_length=500)


class ClosingIn(BaseModel):
    text: str
    example: str
    drafted: bool = False
    declaration: DeclarationIn | None = None
