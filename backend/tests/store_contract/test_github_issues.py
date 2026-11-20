"""The GitHub Store only: issues, comments, restarts, failures."""

from __future__ import annotations

import json
from typing import Any, NoReturn

import httpx
import pytest
from fake_github import FakeGitHub

from app.store import GitHubStore, Kind, StoreUnavailable

from .conftest import ADA, GRACE, SENDS, github_store


def test_first_sign_in_opens_one_labelled_issue_with_a_short_header(
    github: FakeGitHub,
) -> None:
    store = github_store(github)

    store.open_record(ADA)
    store.open_record(ADA)

    (issue,) = github.issues.values()
    assert [label["name"] for label in issue["labels"]] == ["practice"]
    assert "Ada Lovelace" in issue["title"]
    assert (
        "Ada Lovelace" in issue["body"]
        and "OcéENS" in issue["body"]
        and "ada-oceens/OceENS" in issue["body"]
    )
    assert "@" not in issue["body"]  # no mention: GitHub would notify


def test_after_a_restart_the_issue_is_found_again_not_opened_twice(
    github: FakeGitHub,
) -> None:
    github_store(github).open_record(ADA)
    github.issues[999] = {
        **github.issues[401],
        "number": 999,
        "labels": [{"name": "other"}],
    }  # not ours

    restarted = github_store(github)
    restarted.open_record(ADA)
    restarted.open_record(GRACE)

    assert len(github.issues) == 3
    assert github.writes == 2


def test_a_record_survives_a_restart_rebuilt_from_the_comments(
    github: FakeGitHub,
) -> None:
    before = github_store(github)
    before.open_record(ADA)
    first = before.save_answer(ADA, "C1", "guided-calculation", {"sentence": "first"})
    before.save_answer(ADA, "C1", "guided-calculation", {"sentence": "second"})
    before.save_question(ADA, "C1", "read-the-chain", "Why?")
    SENDS[Kind.EVIDENCE_PLAN](before, ADA)

    after = github_store(github)

    assert after.record(ADA) == before.record(ADA)
    assert (
        after.record(ADA).history(Kind.ANSWER, "C1", "guided-calculation")[0] == first
    )
    # and sending after the restart continues the versions
    assert (
        after.save_answer(
            ADA, "C1", "guided-calculation", {"sentence": "third"}
        ).version
        == 3
    )


def test_one_send_is_one_comment_dated_by_github_and_the_body_is_never_rewritten(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    store.open_record(ADA)
    body = github.issues[401]["body"]
    writes = github.writes

    entry = store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "D ≤ 2 h"})

    assert github.writes == writes + 1
    assert github.issues[401]["body"] == body
    (comment,) = github.comments[401]
    assert entry.at.isoformat().replace("+00:00", "Z") == comment["created_at"]


def test_a_send_comment_is_a_line_to_read_then_a_block_to_parse(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "D ≤ 2 h"})
    store.save_question(ADA, "C1", "read-the-chain", "Why 10\nseconds?")

    answer, question = (c["body"] for c in github.comments[401])

    assert answer == (
        "**Answer** to C1, step `guided-calculation` (version 1)\n\n"
        "```json practice\n"
        '{"kind": "answer", "competency": "C1", "step": "guided-calculation", '
        '"version": 1, '
        '"payload": {"fields": {"sentence": "D ≤ 2 h"}}}\n'
        "```\n"
    )
    assert question == (
        "**Question** at C1, step `read-the-chain`:\n\n> Why 10\n> seconds?\n\n"
        "```json practice\n"
        '{"kind": "question", "competency": "C1", "step": "read-the-chain", '
        '"version": 1, '
        '"payload": {"text": "Why 10\\nseconds?"}}\n'
        "```\n"
    )


def test_an_evidence_plan_comment_names_it_and_stores_its_kind(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    SENDS[Kind.EVIDENCE_PLAN](store, ADA)
    SENDS[Kind.EVIDENCE_PANEL_SNAPSHOT](store, ADA)

    plan, snapshot = (c["body"] for c in github.comments[401])

    assert plan.startswith(
        "**Evidence Plan** for C1 (version 1), confirmed at the closing step, "
        "with the Evidence panel as shown; "
        "**Evidence Project** declared: https://github.com/ada/bakery\n\n"
    )
    assert '{"kind": "evidence-plan", "competency": "C1", "version": 1' in plan
    assert '"evidence_panel_snapshot": {"competency": "C1"' in plan
    assert snapshot.startswith(
        "**Evidence panel** as seen at C2's closing step (version 1)\n\n"
    )
    assert '{"kind": "evidence-panel-snapshot", "competency": "C2"' in snapshot


def test_a_declaration_comment_stores_one_for_every_competency(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    SENDS[Kind.DECLARATION](store, ADA)
    store.save_declaration(ADA, {})

    declared, withdrawn = (_block(c["body"]) for c in github.comments[401])

    assert {k: declared[k] for k in ("kind", "competency", "version")} == {
        "kind": "declaration",
        "competency": None,
        "version": 1,
    }
    assert declared["payload"]["url"] == "https://gitlab.com/a/b"
    assert (withdrawn["competency"], withdrawn["version"], withdrawn["payload"]) == (
        None,
        2,
        {},
    )


def _block(body: str) -> dict[str, Any]:
    """The JSON block a send's comment holds."""
    block: dict[str, Any] = json.loads(
        body.split("```json practice\n", 1)[1].split("\n```", 1)[0]
    )
    return block


def test_a_send_before_sign_in_opened_the_issue_opens_it(github: FakeGitHub) -> None:
    github_store(github).save_question(ADA, "C1", "read-the-chain", "?")

    assert len(github.issues) == 1 and len(github.comments[401]) == 1


def test_comments_by_people_are_not_sends(github: FakeGitHub) -> None:
    store = github_store(github)
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "mine"})
    github.comment_by_hand(
        401,
        "Good start.\n\n" + github.comments[401][0]["body"].replace("mine", "forged"),
    )

    entries = github_store(github).record(ADA).entries

    assert [e.payload["fields"]["sentence"] for e in entries] == ["mine"]


def test_comments_by_another_app_are_not_sends(github: FakeGitHub) -> None:
    store = github_store(github)
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "mine"})
    forged = github.comments[401][0]["body"].replace("mine", "forged")
    github.comment_by_hand(401, forged, login="github-actions[bot]", type="Bot")

    entries = github_store(github).record(ADA).entries

    assert [e.payload["fields"]["sentence"] for e in entries] == ["mine"]


def test_a_second_issue_for_the_same_student_drops_nothing_from_their_record(
    github: FakeGitHub,
) -> None:
    # A restart seconds after the first sign-in: the label search does not list
    # the issue yet, so the restarted Store opens a second one for the same
    # Student.
    first = github_store(github)
    first.save_answer(ADA, "C1", "guided-calculation", {"sentence": "first"})
    github.unlisted = {401}
    lagging = github_store(github)
    lagging.open_record(ADA)
    lagging.save_question(ADA, "C1", "read-the-chain", "Why?")
    lagging.save_answer(ADA, "C1", "guided-calculation", {"sentence": "second"})
    github.unlisted = set()
    assert len(github.issues) == 2

    restarted = github_store(github)
    record = restarted.record(ADA)

    assert [(e.kind, e.version) for e in record.entries] == [
        ("answer", 1),
        ("question", 1),
        ("answer", 2),
    ]
    latest = record.latest(Kind.ANSWER, "C1", "guided-calculation")
    assert latest is not None
    assert latest.payload["fields"]["sentence"] == "second"
    assert (
        restarted.save_answer(
            ADA, "C1", "guided-calculation", {"sentence": "third"}
        ).version
        == 3
    )
    restarted.open_record(ADA)
    assert len(github.issues) == 2
    assert [
        e.payload["fields"]["sentence"]
        for e in github_store(github)
        .record(ADA)
        .history(Kind.ANSWER, "C1", "guided-calculation")
    ] == ["first", "second", "third"]


def test_a_long_record_is_read_across_pages() -> None:
    github = FakeGitHub(max_per_page=2)
    store = github_store(github)
    for n in range(5):
        store.save_question(ADA, "C1", "read-the-chain", f"q{n}")

    texts = [e.payload["text"] for e in github_store(github).record(ADA).entries]

    assert texts == ["q0", "q1", "q2", "q3", "q4"]


def test_a_record_once_read_is_kept_in_memory(github: FakeGitHub) -> None:
    store = github_store(github)
    store.save_question(ADA, "C1", "read-the-chain", "?")
    reads = github.reads

    store.record(ADA)
    store.record(ADA)

    assert github.reads == reads


@pytest.mark.parametrize("status", [500, 502, 403, 429])
def test_github_failing_makes_the_store_unavailable_and_loses_nothing_stored(
    github: FakeGitHub, status: int
) -> None:
    store = github_store(github)
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "kept"})
    github.down = status

    with pytest.raises(StoreUnavailable):
        store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "lost"})
    with pytest.raises(StoreUnavailable):
        github_store(github).record(ADA)

    github.down = None
    assert [e.version for e in store.record(ADA).entries] == [1]
    assert (
        store.save_answer(
            ADA, "C1", "guided-calculation", {"sentence": "again"}
        ).version
        == 2
    )


def test_github_unreachable_makes_the_store_unavailable() -> None:
    def unreachable(request: httpx.Request) -> NoReturn:
        raise httpx.ConnectError("no route", request=request)

    store = GitHubStore(
        httpx.Client(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(unreachable),
        ),
        "o/r",
    )

    with pytest.raises(StoreUnavailable):
        store.record(ADA)


def test_the_label_is_a_setting(github: FakeGitHub) -> None:
    github_store(github, label="practice-staging").open_record(ADA)

    assert github_store(github, label="practice").record(ADA).entries == ()
    assert [label["name"] for label in github.issues[401]["labels"]] == [
        "practice-staging"
    ]


def test_a_closed_issue_still_holds_the_record(github: FakeGitHub) -> None:
    github_store(github).save_question(ADA, "C1", "read-the-chain", "?")
    github.issues[401]["state"] = "closed"

    restarted = github_store(github)
    restarted.open_record(ADA)

    assert len(github.issues) == 1
    assert len(restarted.record(ADA).entries) == 1
