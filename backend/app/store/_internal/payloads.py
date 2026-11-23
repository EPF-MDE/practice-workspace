from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.roster import Repository


class Kind(StrEnum):
    ANSWER = "answer"
    DRAWING = "drawing"
    CHECK_POINTS = "check-points"
    SELF_ASSESSMENT = "self-assessment"
    EVIDENCE_PLAN = "evidence-plan"
    DECLARATION = "declaration"
    QUESTION = "question"
    EVIDENCE_PANEL_SNAPSHOT = "evidence-panel-snapshot"


Host = Literal["github", "gitlab"]
GITHUB: Host = "github"
GITLAB: Host = "gitlab"


class Payload(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )
    KIND: ClassVar[Kind]

    def stored(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_defaults=True, by_alias=True)


class AnswerPayload(Payload):
    KIND = Kind.ANSWER
    fields: dict[str, str]


class DrawingPayload(Payload):
    KIND = Kind.DRAWING
    png: str
    png_bytes: int
    snapshot: str
    snapshot_bytes: int
    commit: str | None = None


class CheckPointsPayload(Payload):
    KIND = Kind.CHECK_POINTS
    missed: list[str]


class PointLevelPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    level: str
    link: str | None


class SelfAssessmentPayload(Payload):
    KIND = Kind.SELF_ASSESSMENT
    levels: dict[str, PointLevelPayload]
    missed_check_points: dict[str, list[str]] = Field(default_factory=dict)


class DeclarationPayload(Payload):
    KIND = Kind.DECLARATION
    url: str
    what_to_read: str
    repository: Repository
    host: Host
    access_when_declared: str = Field(alias="access")


class WithdrawalPayload(Payload):
    KIND = Kind.DECLARATION


class EvidencePlanPayload(Payload):
    KIND = Kind.EVIDENCE_PLAN
    text: str
    example: str | None = None
    confirmed: bool = False
    drafted: bool = False
    declaration: DeclarationPayload | None = None
    evidence_panel_snapshot: dict[str, Any] | None = None


class QuestionPayload(Payload):
    KIND = Kind.QUESTION
    text: str


class EvidencePanelSnapshotPayload(Payload):
    model_config = ConfigDict(frozen=True, extra="allow")
    KIND = Kind.EVIDENCE_PANEL_SNAPSHOT


_PAYLOADS: dict[Kind, type[Payload]] = {
    model.KIND: model
    for model in (
        AnswerPayload,
        DrawingPayload,
        CheckPointsPayload,
        SelfAssessmentPayload,
        EvidencePlanPayload,
        DeclarationPayload,
        QuestionPayload,
        EvidencePanelSnapshotPayload,
    )
}


class UnreadablePayload(ValueError):
    pass


def read_payload(kind: Kind, stored: dict[str, Any]) -> Payload:
    if kind == Kind.DECLARATION and not stored:
        return WithdrawalPayload()
    try:
        return _PAYLOADS[kind].model_validate(stored)
    except ValidationError as error:
        raise UnreadablePayload(f"a {kind} entry: {error}") from error
