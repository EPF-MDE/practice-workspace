from __future__ import annotations

import json
from typing import Any

import pytest
from fake_github import FakeGitHub

from app.store import (
    EVERY_COMPETENCY,
    DeclarationPayload,
    DrawingFiles,
    DrawingPayload,
    EvidencePlanPayload,
    Kind,
    QuestionPayload,
    SelfAssessmentPayload,
    WithdrawalPayload,
)
from app.store.github import STORE_BOT

from .conftest import ADA, PNG, SENDS, SNAPSHOT, github_store

WRITTEN: dict[Kind, dict[str, Any]] = {
    Kind.ANSWER: {"fields": {"sentence": "D ≤ 2 h", "unit": "h"}},
    Kind.CHECK_POINTS: {"missed": ["queue", "retry"]},
    Kind.SELF_ASSESSMENT: {
        "levels": {
            "C1.a": {"level": "done", "link": "https://github.com/x/y/pull/3"},
            "C1.b": {"level": "redo", "link": None},
        },
        "missed_check_points": {"redraw": ["queue"]},
    },
    Kind.EVIDENCE_PLAN: {
        "text": "Redo the gate\n\nC1.b, été",
        "example": "my README",
        "confirmed": True,
        "declaration": {
            "url": "https://github.com/ada/bakery",
            "note": "été",
            "repository": "ada/bakery",
            "host": "github",
            "access": "readable",
        },
        "evidence_panel_snapshot": {
            "competency": "C1",
            "facts": [{"point": "C1", "files": []}],
            "files_dropped": True,
        },
    },
    Kind.DECLARATION: {
        "url": "https://gitlab.com/a/b",
        "note": "été",
        "repository": "a/b",
        "host": "gitlab",
        "access": "gitlab",
    },
    Kind.QUESTION: {"text": "Why 10?\nAnd why ``` here?"},
    Kind.EVIDENCE_PANEL_SNAPSHOT: {"empty": False, "facts": [{"point": "C2.c"}]},
}


def _payloads(github: FakeGitHub) -> list[dict[str, Any]]:
    return [
        json.loads(c["body"].split("```json practice\n", 1)[1].split("\n```", 1)[0])[
            "payload"
        ]
        for c in github.comments[401]
    ]


@pytest.mark.parametrize("kind", SENDS)
def test_each_kind_is_written_as_the_json_it_always_was(
    github: FakeGitHub, kind: Kind
) -> None:
    SENDS[kind](github_store(github), ADA)

    assert _payloads(github) == [WRITTEN[kind]]


def test_a_field_left_at_its_default_is_not_written(github: FakeGitHub) -> None:
    store = github_store(github)
    store.send_evidence_plan(ADA, "C1", EvidencePlanPayload(text="plan"))
    store.send_self_assessment(ADA, "C1", SelfAssessmentPayload(levels={}))
    store.withdraw_declaration(ADA)

    assert _payloads(github) == [{"text": "plan"}, {"levels": {}}, {}]


def test_a_drawing_is_written_with_the_commit_holding_its_files(
    github: FakeGitHub,
) -> None:
    github_store(github).send_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)

    snapshot = json.dumps(SNAPSHOT, ensure_ascii=False, separators=(",", ":"))
    assert _payloads(github) == [
        {
            "png": "drawings/ada-oceens/C1/redraw.png",
            "png_bytes": len(PNG),
            "snapshot": "drawings/ada-oceens/C1/redraw.snapshot.json",
            "snapshot_bytes": len(snapshot.encode("utf-8")),
            "commit": github.branches["workspace-data"][-1][0],
        }
    ]


def _sent_before(github: FakeGitHub, block: dict[str, Any]) -> None:
    data = json.dumps(block, ensure_ascii=False, separators=(", ", ": "))
    github.comment_by_hand(
        401, f"A send\n\n```json practice\n{data}\n```\n", STORE_BOT, "Bot"
    )


def test_entries_written_before_read_back_typed(github: FakeGitHub) -> None:
    github_store(github).open_record(ADA)
    _sent_before(
        github,
        {
            "kind": "declaration",
            "competency": None,
            "version": 1,
            "payload": WRITTEN[Kind.DECLARATION],
        },
    )
    _sent_before(
        github,
        {
            "kind": "evidence-plan",
            "competency": "C1",
            "version": 1,
            "payload": {"text": "p", "drafted": True, "kept-by-an-old-engine": 1},
        },
    )
    _sent_before(
        github,
        {"kind": "declaration", "competency": None, "version": 2, "payload": {}},
    )

    record = github_store(github).record(ADA)

    assert [type(e.payload) for e in record.entries] == [
        DeclarationPayload,
        EvidencePlanPayload,
        WithdrawalPayload,
    ]
    plan = record.latest(EvidencePlanPayload, "C1")
    assert plan is not None
    assert (plan.payload.text, plan.payload.drafted, plan.payload.confirmed) == (
        "p",
        True,
        False,
    )
    assert record.latest(WithdrawalPayload, EVERY_COMPETENCY) is not None
    assert record.declaration() is None


def test_a_drawing_written_without_its_commit_reads_from_the_data_branch(
    github: FakeGitHub,
) -> None:
    github_store(github).open_record(ADA)
    github.commit_by_hand("workspace-data", "drawings/ada-oceens/C1/redraw.png", PNG)
    github.commit_by_hand(
        "workspace-data", "drawings/ada-oceens/C1/redraw.snapshot.json", b"{}"
    )
    _sent_before(
        github,
        {
            "kind": "drawing",
            "competency": "C1",
            "drawing": "redraw",
            "version": 1,
            "payload": {
                "png": "drawings/ada-oceens/C1/redraw.png",
                "png_bytes": 3,
                "snapshot": "drawings/ada-oceens/C1/redraw.snapshot.json",
                "snapshot_bytes": 2,
            },
        },
    )

    store = github_store(github)
    drawing = store.record(ADA).latest(DrawingPayload, "C1", "redraw")

    assert drawing is not None
    assert drawing.payload.commit is None
    assert store.drawing(ADA, "C1", "redraw") == DrawingFiles(PNG, {})


def test_a_send_whose_payload_does_not_parse_is_left_out(github: FakeGitHub) -> None:
    store = github_store(github)
    store.send_question(ADA, "C1", "read-the-chain", "kept")
    _sent_before(
        github,
        {
            "kind": "question",
            "competency": "C1",
            "step": "read-the-chain",
            "version": 2,
            "payload": {"words": "not a question's payload"},
        },
    )

    questions = github_store(github).record(ADA).all(QuestionPayload)

    assert [q.payload.text for q in questions] == ["kept"]
