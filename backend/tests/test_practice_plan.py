"""The Practice Plan through the HTTP API: drafted from the levels, filled by
the Transfer, then the Student's own text, which wins, every version dated;
confirmed by the closing step with one example for the Eval.

Signed in as a roster Student, on the fixture content (tests/fixtures/content)
and the in-memory Store. Cut-offs are set through the date settings.
"""

from datetime import datetime
from typing import Any

import pytest
from conftest import ADA, MakeClient, sign_in
from fastapi.testclient import TestClient

from app.roster import Student
from app.settings import Settings
from app.store import InMemoryStore

PAGE = "/api/competencies/C1"
SELF = f"{PAGE}/self-assessment"
DRAFT = f"{PAGE}/practice-plan/draft"
PLAN = f"{PAGE}/practice-plan"
CLOSE = f"{PAGE}/close"
LINK = "https://github.com/ada/notes/pull/4"


def levels(**by_point: str | tuple[str, str]) -> dict[str, Any]:
    out: dict[str, dict[str, str | None]] = {}
    for letter, value in by_point.items():
        level, link = value if isinstance(value, tuple) else (value, None)
        out[f"C1.{letter}"] = {"level": level, "link": link}
    return {"levels": out}


@pytest.fixture
def ada(client: TestClient) -> TestClient:
    sign_in(client, ADA)
    return client


def blocks(text: str) -> list[str]:
    return [b for b in text.split("\n\n") if b.strip()]


def test_the_draft_has_one_block_per_point_rated_and_not_done(ada: TestClient) -> None:
    text = ada.post(
        DRAFT, json=levels(a="understand", b=("done", LINK), e="not-yet")
    ).json()["text"]

    found = blocks(text)
    assert len(found) == 2
    assert found[0].startswith("C1.a")
    assert found[1].startswith("C1.e")
    assert "C1.b" not in text


def test_a_block_holds_the_statement_the_level_the_proof_and_to_get_there_for_that_level(  # noqa: E501
    ada: TestClient,
) -> None:
    (block,) = blocks(ada.post(DRAFT, json=levels(b="understand")).json()["text"])

    assert "C1.b" in block and "Solid" in block and "I understand" in block
    assert "WHERE-STATEMENT" in block
    assert "At the Eval, I will show" in block and "WHERE-PROOF" in block
    assert "To get there: WHERE-UNDERSTAND" in block
    assert "WHERE-NOT-YET" not in block and "WHERE-REDO" not in block


def test_below_i_can_redo_the_draft_points_to_the_course_material_and_from_it_to_the_evidence_project(  # noqa: E501
    ada: TestClient,
) -> None:
    not_yet, understand, redo = blocks(
        ada.post(DRAFT, json=levels(a="not-yet", b="understand", e="redo")).json()[
            "text"
        ]
    )

    assert "course material" in not_yet and "course material" in understand
    assert "Evidence Project" in redo and "course material" not in redo


def test_drafting_stores_nothing(ada: TestClient, store: InMemoryStore) -> None:
    ada.post(DRAFT, json=levels(a="understand"))

    assert store.writes == 0
    assert ada.get(PAGE).json()["self_assessment"] is None


def test_the_page_drafts_the_plan_from_the_levels_sent(ada: TestClient) -> None:
    assert ada.get(PAGE).json()["practice_plan_draft"] == ""

    ada.post(SELF, json=levels(a="redo"))

    page = ada.get(PAGE).json()
    assert "WHY-REDO" in page["practice_plan_draft"]
    assert page["practice_plan"] is None


def test_the_transfer_fills_its_points_to_get_there(ada: TestClient) -> None:
    page = ada.get(PAGE).json()
    transfer = next(s for s in page["steps"] if s["id"] == "transfer")
    assert (transfer["kind"], transfer["fills"]) == ("transfer", "C1.b")

    ada.post(
        f"{PAGE}/steps/transfer/answer",
        json={"fields": {"project": "ada/bakery", "requirement": "TRANSFER-PLAN"}},
    )

    (block,) = blocks(ada.post(DRAFT, json=levels(b="understand")).json()["text"])
    assert "ada/bakery" in block and "TRANSFER-PLAN" in block
    assert "WHERE-UNDERSTAND" not in block


def test_the_transfer_defaults_to_the_evidence_project(
    ada: TestClient, store: InMemoryStore
) -> None:
    ada.post(
        f"{PAGE}/declaration",
        json={"url": "https://github.com/ada/best", "note": "The README"},
    )

    assert ada.get(PAGE).json()["evidence_project"] == "https://github.com/ada/best"
    ada.post(
        f"{PAGE}/steps/transfer/answer",
        json={"fields": {"project": "", "requirement": "TRANSFER-PLAN"}},
    )

    (block,) = blocks(ada.post(DRAFT, json=levels(b="redo")).json()["text"])
    assert "on https://github.com/ada/best" in block


def _ada(client: TestClient) -> Student:
    return Student(**client.get("/api/me").json())


def test_the_students_text_wins_over_the_draft_and_every_version_is_dated(
    ada: TestClient,
) -> None:
    ada.post(SELF, json=levels(a="understand", b="redo"))

    first = ada.post(PLAN, json={"text": "Only C1.b, my way."})
    second = ada.post(PLAN, json={"text": "Only C1.b, my way.\nAnd a line of my own."})

    assert first.status_code == second.status_code == 200
    plan = ada.get(PAGE).json()["practice_plan"]
    assert plan["text"] == "Only C1.b, my way.\nAnd a line of my own."
    assert [(v["version"], v["sent_at"]) for v in plan["history"]] == [
        (1, first.json()["sent_at"]),
        (2, second.json()["sent_at"]),
    ]


def test_a_line_removed_from_the_plan_leaves_the_points_level_unchanged(
    ada: TestClient,
) -> None:
    ada.post(SELF, json=levels(a="understand", b="redo"))

    ada.post(PLAN, json={"text": "Nothing about C1.a any more."})

    assert (
        ada.get(PAGE).json()["self_assessment"]["levels"]["C1.a"]["level"]
        == "understand"
    )


def test_the_closing_step_confirms_the_plan_with_one_example_for_the_eval_in_one_send(
    ada: TestClient, store: InMemoryStore
) -> None:
    ada.post(SELF, json=levels(a="understand"))
    before = store.writes

    closed = ada.post(
        CLOSE, json={"text": "My plan.", "example": "The README of ada/bakery, line 3."}
    )

    assert closed.status_code == 200
    assert store.writes == before + 1
    plan = ada.get(PAGE).json()["practice_plan"]
    assert (plan["text"], plan["example"], plan["confirmed"]) == (
        "My plan.",
        "The README of ada/bakery, line 3.",
        True,
    )


def test_the_closing_step_needs_an_example_and_a_self_assessment(
    ada: TestClient,
) -> None:
    assert ada.post(CLOSE, json={"text": "My plan.", "example": "x"}).status_code == 409
    ada.post(SELF, json=levels(a="understand"))
    assert ada.post(CLOSE, json={"text": "My plan.", "example": " "}).status_code == 422


def test_an_edit_after_the_closing_step_keeps_the_example_and_the_confirmation(
    ada: TestClient,
) -> None:
    ada.post(SELF, json=levels(a="understand"))
    ada.post(CLOSE, json={"text": "My plan.", "example": "The README."})

    ada.post(PLAN, json={"text": "My plan, adjusted."})

    plan = ada.get(PAGE).json()["practice_plan"]
    assert (plan["text"], plan["example"], plan["confirmed"], plan["version"]) == (
        "My plan, adjusted.",
        "The README.",
        True,
        2,
    )


def test_the_plan_stays_editable_after_the_close_until_the_reading_day(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = make_client(
        settings=test_settings.model_copy(
            update={"closes_at": future, "reading_day_at": future}
        )
    )
    sign_in(before, ADA)
    before.post(SELF, json=levels(a="understand"))
    closed = make_client(
        settings=test_settings.model_copy(
            update={"closes_at": past, "reading_day_at": future}
        )
    )
    sign_in(closed, ADA)
    over = make_client(
        settings=test_settings.model_copy(
            update={"closes_at": past, "reading_day_at": past}
        )
    )
    sign_in(over, ADA)

    assert (
        closed.post(CLOSE, json={"text": "Plan.", "example": "Example."}).status_code
        == 200
    )
    assert closed.post(PLAN, json={"text": "Plan, later."}).status_code == 200
    refused = over.post(PLAN, json={"text": "Too late."})
    assert refused.status_code == 403
    assert "Reading Day" in refused.json()["detail"]
    assert (
        over.post(CLOSE, json={"text": "Too late.", "example": "x"}).status_code == 403
    )


def test_confirming_the_untouched_draft_keeps_it_a_draft_that_follows_later_level_moves(
    ada: TestClient,
) -> None:
    ada.post(SELF, json=levels(a="understand"))
    draft = ada.get(PAGE).json()["practice_plan_draft"]

    closed = ada.post(
        CLOSE, json={"text": draft, "example": "The README.", "drafted": True}
    )

    assert closed.status_code == 200
    assert closed.json()["drafted"] is True
    ada.post(SELF, json=levels(a="understand", b="redo"))
    page = ada.get(PAGE).json()
    assert (
        page["practice_plan"]["drafted"] is True
    )  # not the Student's text: the page offers the new draft
    assert (
        page["practice_plan_draft"] != draft and "C1.b" in page["practice_plan_draft"]
    )
    assert page["practice_plan"]["confirmed"] is True


def test_a_text_equal_to_the_draft_is_a_draft_even_unflagged(ada: TestClient) -> None:
    ada.post(SELF, json=levels(a="understand"))
    draft = ada.get(PAGE).json()["practice_plan_draft"]

    closed = ada.post(CLOSE, json={"text": draft, "example": "The README."})

    assert closed.json()["drafted"] is True


def test_only_an_edit_makes_the_plan_the_students_text(ada: TestClient) -> None:
    ada.post(SELF, json=levels(a="understand"))
    draft = ada.get(PAGE).json()["practice_plan_draft"]
    ada.post(CLOSE, json={"text": draft, "example": "The README.", "drafted": True})

    edited = ada.post(PLAN, json={"text": draft + "\nAnd a line of my own."})

    assert edited.json()["drafted"] is False
    ada.post(SELF, json=levels(a="understand", b="redo"))
    plan = ada.get(PAGE).json()["practice_plan"]
    assert (plan["drafted"], plan["text"], plan["confirmed"]) == (
        False,
        draft + "\nAnd a line of my own.",
        True,
    )
