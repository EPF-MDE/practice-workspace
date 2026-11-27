from conftest import (
    AFTER_THE_CLOSE,
    AFTER_THE_READING_DAY,
    BEFORE_THE_CLOSE,
    MakeClient,
    c1_levels,
    sign_in,
)
from courses_under_test import OnTheRoster
from fastapi.testclient import TestClient

from app.store import InMemoryStore

PAGE = "/api/competencies/C1"
SELF = f"{PAGE}/self-assessment"
DRAFT = f"{PAGE}/evidence-plan/draft"
PLAN = f"{PAGE}/evidence-plan"
CLOSE = f"{PAGE}/close"
LINK = "https://github.com/ada/notes/pull/4"


def blocks(text: str) -> list[str]:
    return [b for b in text.split("\n\n") if b.strip()]


def test_the_draft_has_one_block_per_point_rated_and_not_done(
    signed_in: TestClient,
) -> None:
    text = signed_in.post(
        DRAFT, json=c1_levels(a="understand", b=("done", LINK), e="not-yet")
    ).json()["text"]

    found = blocks(text)
    assert len(found) == 2
    assert found[0].startswith("C1.a")
    assert found[1].startswith("C1.e")
    assert "C1.b" not in text


def test_a_block_holds_the_statement_the_level_the_proof_and_to_get_there_for_that_level(  # noqa: E501
    signed_in: TestClient,
) -> None:
    (block,) = blocks(
        signed_in.post(DRAFT, json=c1_levels(b="understand")).json()["text"]
    )

    assert "C1.b" in block and "Solid" in block and "I understand" in block
    assert "WHERE-STATEMENT" in block
    assert "At the Eval, I will show" in block and "WHERE-PROOF" in block
    assert "To get there: WHERE-UNDERSTAND" in block
    assert "WHERE-NOT-YET" not in block and "WHERE-REDO" not in block


def test_below_i_can_redo_the_draft_points_to_the_course_material_and_from_it_to_the_evidence_project(  # noqa: E501
    signed_in: TestClient,
) -> None:
    not_yet, understand, redo = blocks(
        signed_in.post(
            DRAFT, json=c1_levels(a="not-yet", b="understand", e="redo")
        ).json()["text"]
    )

    assert "course material" in not_yet and "course material" in understand
    assert "Evidence Project" in redo and "course material" not in redo


def test_drafting_stores_nothing(signed_in: TestClient, store: InMemoryStore) -> None:
    signed_in.post(DRAFT, json=c1_levels(a="understand"))

    assert store.writes == 0
    assert signed_in.get(PAGE).json()["self_assessment"] is None


def test_the_page_drafts_the_plan_from_the_levels_sent(signed_in: TestClient) -> None:
    assert signed_in.get(PAGE).json()["evidence_plan_draft"] == ""

    signed_in.post(SELF, json=c1_levels(a="redo"))

    page = signed_in.get(PAGE).json()
    assert "WHY-REDO" in page["evidence_plan_draft"]
    assert page["evidence_plan"] is None


def test_the_transfer_fills_its_points_to_get_there(signed_in: TestClient) -> None:
    page = signed_in.get(PAGE).json()
    transfer = next(s for s in page["steps"] if s["id"] == "transfer")
    assert (transfer["kind"], transfer["fills"]) == ("transfer", "C1.b")

    signed_in.post(
        f"{PAGE}/steps/transfer/answer",
        json={"fields": {"project": "ada/bakery", "requirement": "TRANSFER-PLAN"}},
    )

    (block,) = blocks(
        signed_in.post(DRAFT, json=c1_levels(b="understand")).json()["text"]
    )
    assert "ada/bakery" in block and "TRANSFER-PLAN" in block
    assert "WHERE-UNDERSTAND" not in block


def test_the_transfer_defaults_to_the_evidence_project(
    signed_in: TestClient, store: InMemoryStore
) -> None:
    signed_in.post(
        "/api/evidence-project/declaration",
        json={"url": "https://github.com/ada/best", "what_to_read": "The README"},
    )

    assert (
        signed_in.get(PAGE).json()["evidence_project"] == "https://github.com/ada/best"
    )
    signed_in.post(
        f"{PAGE}/steps/transfer/answer",
        json={"fields": {"project": "", "requirement": "TRANSFER-PLAN"}},
    )

    (block,) = blocks(signed_in.post(DRAFT, json=c1_levels(b="redo")).json()["text"])
    assert "on https://github.com/ada/best" in block


def test_the_students_text_wins_over_the_draft_and_every_version_is_dated(
    signed_in: TestClient,
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand", b="redo"))

    first = signed_in.post(PLAN, json={"text": "Only C1.b, my way."})
    second = signed_in.post(
        PLAN, json={"text": "Only C1.b, my way.\nAnd a line of my own."}
    )

    assert first.status_code == second.status_code == 200
    plan = signed_in.get(PAGE).json()["evidence_plan"]
    assert plan["text"] == "Only C1.b, my way.\nAnd a line of my own."
    assert [(v["version"], v["sent_at"]) for v in plan["history"]] == [
        (1, first.json()["sent_at"]),
        (2, second.json()["sent_at"]),
    ]


def test_a_line_removed_from_the_plan_leaves_the_points_level_unchanged(
    signed_in: TestClient,
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand", b="redo"))

    signed_in.post(PLAN, json={"text": "Nothing about C1.a any more."})

    assert (
        signed_in.get(PAGE).json()["self_assessment"]["levels"]["C1.a"]["level"]
        == "understand"
    )


def test_the_closing_step_confirms_the_plan_with_one_example_for_the_eval_in_one_send(
    signed_in: TestClient, store: InMemoryStore
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand"))
    before = store.writes

    closed = signed_in.post(
        CLOSE, json={"text": "My plan.", "example": "The README of ada/bakery, line 3."}
    )

    assert closed.status_code == 200
    assert store.writes == before + 1
    plan = signed_in.get(PAGE).json()["evidence_plan"]
    assert (plan["text"], plan["example"], plan["confirmed"]) == (
        "My plan.",
        "The README of ada/bakery, line 3.",
        True,
    )


def test_the_closing_step_needs_an_example_and_a_self_assessment(
    signed_in: TestClient,
) -> None:
    assert (
        signed_in.post(CLOSE, json={"text": "My plan.", "example": "x"}).status_code
        == 409
    )
    signed_in.post(SELF, json=c1_levels(a="understand"))
    assert (
        signed_in.post(CLOSE, json={"text": "My plan.", "example": " "}).status_code
        == 422
    )


def test_an_edit_after_the_closing_step_keeps_the_example_and_the_confirmation(
    signed_in: TestClient,
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand"))
    signed_in.post(CLOSE, json={"text": "My plan.", "example": "The README."})

    signed_in.post(PLAN, json={"text": "My plan, adjusted."})

    plan = signed_in.get(PAGE).json()["evidence_plan"]
    assert (plan["text"], plan["example"], plan["confirmed"], plan["version"]) == (
        "My plan, adjusted.",
        "The README.",
        True,
        2,
    )


def test_the_plan_stays_editable_after_the_close_until_the_reading_day(
    make_client: MakeClient,
    student: OnTheRoster,
) -> None:
    before = make_client(clock=lambda: BEFORE_THE_CLOSE)
    sign_in(before, student.github_id)
    before.post(SELF, json=c1_levels(a="understand"))
    closed = make_client(clock=lambda: AFTER_THE_CLOSE)
    sign_in(closed, student.github_id)
    over = make_client(clock=lambda: AFTER_THE_READING_DAY)
    sign_in(over, student.github_id)

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
    signed_in: TestClient,
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand"))
    draft = signed_in.get(PAGE).json()["evidence_plan_draft"]

    closed = signed_in.post(
        CLOSE, json={"text": draft, "example": "The README.", "drafted": True}
    )

    assert closed.status_code == 200
    assert closed.json()["drafted"] is True
    signed_in.post(SELF, json=c1_levels(a="understand", b="redo"))
    page = signed_in.get(PAGE).json()
    assert page["evidence_plan"]["drafted"] is True, "not the Student's text"
    assert (
        page["evidence_plan_draft"] != draft and "C1.b" in page["evidence_plan_draft"]
    ), "the page offers the new draft"
    assert page["evidence_plan"]["confirmed"] is True


def test_a_text_equal_to_the_draft_is_a_draft_even_unflagged(
    signed_in: TestClient,
) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand"))
    draft = signed_in.get(PAGE).json()["evidence_plan_draft"]

    closed = signed_in.post(CLOSE, json={"text": draft, "example": "The README."})

    assert closed.json()["drafted"] is True


def test_only_an_edit_makes_the_plan_the_students_text(signed_in: TestClient) -> None:
    signed_in.post(SELF, json=c1_levels(a="understand"))
    draft = signed_in.get(PAGE).json()["evidence_plan_draft"]
    signed_in.post(
        CLOSE, json={"text": draft, "example": "The README.", "drafted": True}
    )

    edited = signed_in.post(PLAN, json={"text": draft + "\nAnd a line of my own."})

    assert edited.json()["drafted"] is False
    signed_in.post(SELF, json=c1_levels(a="understand", b="redo"))
    plan = signed_in.get(PAGE).json()["evidence_plan"]
    assert (plan["drafted"], plan["text"], plan["confirmed"]) == (
        False,
        draft + "\nAnd a line of my own.",
        True,
    )
