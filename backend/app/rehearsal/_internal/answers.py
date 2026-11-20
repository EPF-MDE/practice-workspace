"""The page, and what a Student sends at a step: answers, questions, drawings."""

from __future__ import annotations

import base64
import binascii
import json

from fastapi import Depends, HTTPException, Request

from app.auth import current_student
from app.content import (
    Answer,
    Page,
    Step,
)
from app.roster import Student
from app.settings import Settings
from app.store import Kind

from .models import (
    MAX_FIELD_CHARS,
    MAX_PNG_BYTES,
    MAX_SNAPSHOT_BYTES,
    PNG_SIGNATURE,
    AnswerIn,
    AnswerSent,
    CheckPointsIn,
    CheckPointsSent,
    CompetencyPage,
    DrawingIn,
    DrawingStored,
    MyDrawing,
    Question,
    QuestionIn,
    _at_most,
)
from .review import (
    _draft,
    _evidence_plan,
    _evidence_project,
    _self_assessment,
)
from .router import router
from .steps import (
    _closed,
    _drawing_sent,
    _hints,
    _page,
    _phase,
    _reference,
    _refuse_if_closed,
    _step,
    _step_out,
    _store,
    _waits_for,
)


@router.get("/api/competencies/{competency}", tags=["rehearsal"])
def competency_page(
    competency: str, request: Request, student: Student = Depends(current_student)
) -> CompetencyPage:
    """A Competency's long page for the Student's Group, each answer locked until their
    own is sent."""
    page = _page(request, competency, student)
    record = _store(request).record(student)
    settings: Settings = request.app.state.settings
    hints = _hints(page, record)
    assessment = record.latest(Kind.SELF_ASSESSMENT, page.competency)
    return CompetencyPage(
        competency=page.competency,
        title=page.title,
        intro_html=page.intro_html,
        steps=[_step_out(step, page, record, hints) for step in page.steps],
        closes_at=settings.closes_at,
        closed=_closed(settings),
        reading_day_at=settings.reading_day_at,
        reading_day_passed=_phase(settings) == "over",
        self_assessment=_self_assessment(record, page.competency),
        evidence_plan=_evidence_plan(record, page.competency),
        evidence_plan_draft=_draft(
            page, record, assessment.payload["levels"] if assessment else {}
        ),
        evidence_project=_evidence_project(record),
        tldraw_license_key=settings.tldraw_license_key,
    )


@router.post(
    "/api/competencies/{competency}/steps/{step_id}/answer", tags=["rehearsal"]
)
def send_answer(
    competency: str,
    step_id: str,
    answer: AnswerIn,
    request: Request,
    student: Student = Depends(current_student),
) -> AnswerSent:
    """Store the Student's answer to a step (a new version each time) and release its
    answer blocks."""
    page = _page(request, competency, student)
    step = _step(page, step_id)
    field_ids = {f.id for f in step.fields}
    if not field_ids:
        raise HTTPException(422, "This step takes no answer")
    unknown = set(answer.fields) - field_ids
    if unknown:
        raise HTTPException(
            422, f"Not a field of this step: {', '.join(sorted(unknown))}"
        )
    if not any(text.strip() for text in answer.fields.values()):
        raise HTTPException(422, "Write something in at least one field before sending")
    for field_id, text in answer.fields.items():
        _at_most(text, MAX_FIELD_CHARS, f"Your answer in '{field_id}'")
    not_an_option = sorted(
        f.id
        for f in step.fields
        if f.options and answer.fields.get(f.id, "") not in ("", *f.options)
    )
    if not_an_option:
        raise HTTPException(
            422, f"Pick one of the options offered: {', '.join(not_an_option)}"
        )
    _refuse_if_closed(request.app.state.settings, "answers")
    waits_for = _waits_for(step, page, _store(request).record(student))
    if waits_for:
        raise HTTPException(
            409,
            f"Send your answer to “{waits_for.title}” first: this step starts from it.",
        )
    entry = _store(request).save_answer(student, competency, step_id, answer.fields)
    return AnswerSent(
        version=entry.version,
        sent_at=entry.at,
        unlocked=[b.html for b in step.blocks if isinstance(b, Answer)],
    )


@router.post(
    "/api/competencies/{competency}/steps/{step_id}/questions", tags=["rehearsal"]
)
def ask_question(
    competency: str,
    step_id: str,
    question: QuestionIn,
    request: Request,
    student: Student = Depends(current_student),
) -> Question:
    """Store a question, with its Competency and step, for the Instructor."""
    _step(_page(request, competency, student), step_id)
    if not question.text.strip():
        raise HTTPException(422, "Write your question before sending it")
    _refuse_if_closed(request.app.state.settings, "questions")
    entry = _store(request).save_question(
        student, competency, step_id, question.text.strip()
    )
    return Question(text=entry.payload["text"], asked_at=entry.at)


def _drawing_step(page: Page, step_id: str) -> Step:
    step = _step(page, step_id)
    if step.kind != "drawing":
        raise HTTPException(422, "This step takes no drawing")
    return step


def _png(png_base64: str) -> bytes:
    if len(png_base64) > MAX_PNG_BYTES * 4 // 3 + 4:
        raise HTTPException(
            413,
            "This drawing is too large to send: remove an image pasted into it, then "
            "try again",
        )
    try:
        png = base64.b64decode(png_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "The drawing's image could not be read") from error
    if not png.startswith(PNG_SIGNATURE):
        raise HTTPException(422, "The drawing's image is not a PNG")
    return png


@router.post(
    "/api/competencies/{competency}/steps/{step_id}/drawing", tags=["rehearsal"]
)
def send_drawing(
    competency: str,
    step_id: str,
    drawing: DrawingIn,
    request: Request,
    student: Student = Depends(current_student),
) -> DrawingStored:
    """Store the Student's drawing (its PNG and tldraw snapshot, a new version each
    time) and release the Reference Drawing with its check points."""
    step = _drawing_step(_page(request, competency, student), step_id)
    png = _png(drawing.png_base64)
    if not isinstance(drawing.snapshot.get("document"), dict):
        raise HTTPException(422, "The drawing's snapshot is not a tldraw snapshot")
    if len(json.dumps(drawing.snapshot, ensure_ascii=False)) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(
            413,
            "This drawing is too large to send: remove an image pasted into it, then "
            "try again",
        )
    _refuse_if_closed(request.app.state.settings, "drawings")
    entry = _store(request).save_drawing(
        student, competency, step_id, png, drawing.snapshot
    )
    reference = step.reference
    return DrawingStored(
        **_drawing_sent(entry).model_dump(),
        reference=_reference(reference, True) if reference else None,
        unlocked=[b.html for b in step.blocks if isinstance(b, Answer)],
    )


@router.get(
    "/api/competencies/{competency}/steps/{step_id}/drawing", tags=["rehearsal"]
)
def my_drawing(
    competency: str,
    step_id: str,
    request: Request,
    student: Student = Depends(current_student),
) -> MyDrawing:
    """The Student's latest drawing for a step, to draw on again in a browser that has
    no copy."""
    _drawing_step(_page(request, competency, student), step_id)
    store = _store(request)
    entry = store.record(student).latest(Kind.DRAWING, competency, step_id)
    files = store.drawing(student, competency, step_id) if entry else None
    if entry is None or files is None:
        raise HTTPException(404, "No drawing sent for this step yet")
    return MyDrawing(version=entry.version, sent_at=entry.at, snapshot=files.snapshot)


@router.post(
    "/api/competencies/{competency}/steps/{step_id}/check-points", tags=["rehearsal"]
)
def tick_missed_check_points(
    competency: str,
    step_id: str,
    ticks: CheckPointsIn,
    request: Request,
    student: Student = Depends(current_student),
) -> CheckPointsSent:
    """Store which of the Reference Drawing's check points the Student's drawing
    missed."""
    step = _drawing_step(_page(request, competency, student), step_id)
    reference = step.reference
    known = [c.id for c in reference.check_points] if reference else []
    unknown = set(ticks.missed) - set(known)
    if unknown:
        raise HTTPException(
            422, f"Not a check point of this drawing: {', '.join(sorted(unknown))}"
        )
    _refuse_if_closed(request.app.state.settings, "check points")
    store = _store(request)
    if store.record(student).latest(Kind.DRAWING, competency, step_id) is None:
        raise HTTPException(
            409,
            "Send your drawing first: the check points come with the Reference Drawing",
        )
    missed = [
        c for c in known if c in ticks.missed
    ]  # in the reference's order, once each
    entry = store.save_missed_check_points(student, competency, step_id, missed)
    return CheckPointsSent(
        missed=entry.payload["missed"], version=entry.version, sent_at=entry.at
    )
