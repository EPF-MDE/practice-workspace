from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException, Request

from app import closing
from app.content import (
    Answer,
    Block,
    Canvas,
    Competency,
    ExampleDrawing,
    Html,
    Page,
    Point,
    ReferenceDrawing,
    Step,
    Waiting,
)
from app.content import Field as ContentField
from app.roster import Student
from app.settings import PARIS, Settings
from app.store import Entry, Kind, Record, Store

from .models import (
    AnswerBlock,
    CanvasBlock,
    CheckPointOut,
    DrawingSent,
    ExampleDrawingBlock,
    FieldBlock,
    HtmlBlock,
    PointBlock,
    Question,
    ReferenceDrawingBlock,
    Sent,
    SentVersion,
    StepOut,
    WaitingBlock,
    WaitsFor,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _closed(settings: Settings) -> bool:
    return _now() > settings.closes_at


def _phase(settings: Settings) -> closing.Phase:
    return closing.phase(_now(), settings.closes_at, settings.reading_day_at)


def _refuse_after_the_reading_day(settings: Settings, what: str) -> None:
    if _phase(settings) == "over":
        when = settings.reading_day_at.astimezone(PARIS).strftime("%-d %B %Y at %H:%M")
        raise HTTPException(
            403,
            f"The Reading Day passed on {when}, Paris time: {what} can no longer "
            "change.",
        )


def _refuse_if_closed(settings: Settings, what: str) -> None:
    if _closed(settings):
        when = settings.closes_at.astimezone(PARIS).strftime("%-d %B %Y at %H:%M")
        raise HTTPException(
            403,
            f"The workspace closed on {when}, Paris time: {what} can no longer be "
            "sent.",
        )


def _unlocked(step: Step, record: Record, competency: str) -> bool:
    if step.kind == "drawing":
        return record.latest(Kind.DRAWING, competency, step.id) is not None
    return (
        bool(step.fields)
        and record.latest(Kind.ANSWER, competency, step.id) is not None
    )


def _waits_for(step: Step, page: Page, record: Record) -> Step | None:
    before = page.step(step.after) if step.after else None
    return before if before and not _unlocked(before, record, page.competency) else None


def _reference(block: ReferenceDrawing, unlocked: bool) -> ReferenceDrawingBlock:
    if not unlocked:
        return ReferenceDrawingBlock(
            locked=True, snapshot=None, caption_html=None, check_points=None
        )
    return ReferenceDrawingBlock(
        locked=False,
        snapshot=block.snapshot,
        caption_html=block.caption_html,
        check_points=[
            CheckPointOut(id=c.id, point=c.point, html=c.html)
            for c in block.check_points
        ],
    )


def _block(
    block: Block,
    unlocked: bool,
    hints: dict[str, list[CheckPointOut]],
    after: str = "",
) -> (
    HtmlBlock
    | FieldBlock
    | AnswerBlock
    | PointBlock
    | ExampleDrawingBlock
    | CanvasBlock
    | ReferenceDrawingBlock
    | WaitingBlock
):
    match block:
        case Waiting(html=html):
            return WaitingBlock(step=after, html=html)
        case Html(html=html):
            return HtmlBlock(html=html)
        case ContentField(id=id, kind=kind, label_html=label, options=options):
            return FieldBlock(
                id=id, kind=kind, label_html=label, options=list(options) or None
            )
        case Answer(html=html):
            return AnswerBlock(locked=not unlocked, html=html if unlocked else None)
        case Point():
            return PointBlock(
                id=block.id,
                band=block.band,
                statement_html=block.statement_html,
                proof_html=block.proof_html,
                to_get_there_html=block.to_get_there_html,
                missed_check_points=hints.get(block.id, []),
            )
        case ExampleDrawing(snapshot=snapshot, caption_html=caption):
            return ExampleDrawingBlock(snapshot=snapshot, caption_html=caption)
        case Canvas(prompt_html=prompt):
            return CanvasBlock(prompt_html=prompt)
        case ReferenceDrawing():
            return _reference(block, unlocked)
    raise TypeError(block)


def _drawing_sent(entry: Entry) -> DrawingSent:
    return DrawingSent(
        version=entry.version,
        sent_at=entry.at,
        png_bytes=entry.payload["png_bytes"],
        snapshot_bytes=entry.payload["snapshot_bytes"],
    )


def _version(entry: Entry) -> SentVersion:
    return SentVersion(
        fields=entry.payload["fields"], version=entry.version, sent_at=entry.at
    )


def _hints(page: Page, record: Record) -> dict[str, list[CheckPointOut]]:
    hints: dict[str, list[CheckPointOut]] = {}
    for step in page.steps:
        reference = step.reference
        missed = (
            record.missed_check_points(page.competency, step.id) if reference else None
        )
        if not (reference and missed):
            continue
        for check in reference.check_points:
            if check.id in missed:
                hints.setdefault(check.point, []).append(
                    CheckPointOut(id=check.id, point=check.point, html=check.html)
                )
    return hints


def _step_out(
    step: Step, page: Page, record: Record, hints: dict[str, list[CheckPointOut]]
) -> StepOut:
    competency = page.competency
    waits_for = _waits_for(step, page, record)
    history = record.history(Kind.ANSWER, competency, step.id)
    sent = (
        Sent(
            **_version(history[-1]).model_dump(), history=[_version(e) for e in history]
        )
        if history
        else None
    )
    unlocked = _unlocked(step, record, competency)
    drawing = record.latest(Kind.DRAWING, competency, step.id)
    missed = record.missed_check_points(competency, step.id)
    return StepOut(
        id=step.id,
        title=step.title,
        minutes=step.minutes,
        kind=step.kind,
        fills=step.fills,
        optional=step.optional,
        blocks=[
            _block(b, unlocked, hints, step.after or "")
            for b in (step.waiting if waits_for else step.blocks)
        ],
        waits_for=WaitsFor(step=waits_for.id, title=waits_for.title)
        if waits_for
        else None,
        sent=sent,
        drawing=_drawing_sent(drawing) if drawing else None,
        missed_check_points=missed,
        questions=[
            Question(text=e.payload["text"], asked_at=e.at)
            for e in record.all(Kind.QUESTION, competency)
            if e.key == step.id
        ],
    )


def _store(request: Request) -> Store:
    return cast(Store, request.app.state.store)


def _page(request: Request, competency: str, student: Student) -> Page:
    content: dict[str, Competency] = request.app.state.content
    if competency not in content:
        raise HTTPException(404, f"No Competency {competency}")
    return content[competency].for_group(student.group)


def _step(page: Page, step_id: str) -> Step:
    step = page.step(step_id)
    if step is None:
        raise HTTPException(404, f"No step {step_id} in {page.competency}")
    return step
