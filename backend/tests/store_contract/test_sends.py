"""The Store's contract for every kind of send but drawings, on both Stores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fake_github import FakeGitHub

from app.roster import Student
from app.store import MAX_SEND_CHARS, Kind, SendTooLarge, Store

from .conftest import ADA, GRACE, SENDS, github_store


def test_a_record_is_empty_before_any_send(store: Store) -> None:
    assert store.record(ADA).entries == ()


def test_an_answer_is_read_back_as_the_current_state(store: Store) -> None:
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "D is at most 2 h"})

    latest = store.record(ADA).latest(Kind.ANSWER, "C1", "guided-calculation")

    assert latest is not None
    assert latest.payload == {"fields": {"sentence": "D is at most 2 h"}}
    assert latest.version == 1


def test_each_send_is_a_new_version_and_every_version_is_kept(store: Store) -> None:
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "first"})
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "second"})
    store.save_answer(ADA, "C1", "the-number-changes", {"what-moves": "D"})

    record = store.record(ADA)

    history = record.history(Kind.ANSWER, "C1", "guided-calculation")
    assert [(e.version, e.payload["fields"]["sentence"]) for e in history] == [
        (1, "first"),
        (2, "second"),
    ]
    assert history[0].at < history[1].at
    other = record.latest(Kind.ANSWER, "C1", "the-number-changes")
    assert other is not None
    assert other.version == 1


@pytest.mark.parametrize("kind", SENDS)
def test_every_kind_reads_back_as_sent(store: Store, kind: Kind) -> None:
    sent = SENDS[kind](store, ADA)

    read = store.record(ADA).latest(kind, sent.competency, sent.key)

    assert read is not None
    assert (read.kind, read.competency, read.key, read.payload, read.version) == (
        kind,
        sent.competency,
        sent.key,
        sent.payload,
        1,
    )
    assert read.at == sent.at


def test_a_send_too_large_for_one_github_comment_is_refused_and_stores_nothing(
    store: Store,
) -> None:
    store.save_practice_plan(ADA, "C1", {"text": "kept"})

    with pytest.raises(SendTooLarge):
        store.save_practice_plan(ADA, "C1", {"text": "x" * MAX_SEND_CHARS})
    # JSON escaping counts: a newline is stored as two characters
    with pytest.raises(SendTooLarge):
        store.save_practice_plan(ADA, "C1", {"text": "\n" * (MAX_SEND_CHARS // 2 + 1)})

    assert [e.payload["text"] for e in store.record(ADA).entries] == ["kept"]
    assert (
        store.save_practice_plan(
            ADA, "C1", {"text": "y" * (MAX_SEND_CHARS - 100)}
        ).version
        == 2
    )


def test_the_largest_send_accepted_fits_one_github_comment(github: FakeGitHub) -> None:
    store = github_store(github)
    text = "é\n" * ((MAX_SEND_CHARS - 100) // 3)  # escaped, about MAX_SEND_CHARS

    store.save_question(
        ADA, "C1", "read-the-chain", text
    )  # its line quotes the text once more
    store.save_practice_plan(
        ADA, "C1", {"text": "y" * (MAX_SEND_CHARS - 100), "confirmed": True}
    )

    assert len(github_store(github).record(ADA).entries) == 2


def test_every_question_is_kept_with_its_step(store: Store) -> None:
    store.save_question(ADA, "C1", "read-the-chain", "First")
    store.save_question(ADA, "C1", "guided-calculation", "Second")
    store.save_question(ADA, "C2", "read-the-chain", "Third")

    questions = store.record(ADA).all(Kind.QUESTION, "C1")

    assert [(q.key, q.payload["text"]) for q in questions] == [
        ("read-the-chain", "First"),
        ("guided-calculation", "Second"),
    ]


def test_an_empty_declaration_withdraws_the_last_one(store: Store) -> None:
    store.save_declaration(ADA, "C3", {"url": "https://github.com/a/b"})
    store.save_declaration(ADA, "C3", {})

    latest = store.record(ADA).latest(Kind.DECLARATION, "C3")
    assert latest is not None
    assert latest.payload == {}


def test_the_declaration_now_is_the_latest_sent_alone_or_with_the_closing_step(
    store: Store,
) -> None:
    assert store.record(ADA).declaration("C2") is None
    store.save_declaration(
        ADA, "C2", {"url": "https://github.com/ada/a", "note": "first"}
    )
    store.save_practice_plan(
        ADA,
        "C2",
        {"text": "p", "declaration": {"url": "https://github.com/ada/b", "note": "n"}},
    )
    store.save_declaration(
        ADA, "C3", {"url": "https://github.com/ada/c", "note": "other Competency"}
    )

    declaration = store.record(ADA).declaration("C2")
    assert declaration is not None
    payload, at = declaration
    assert payload["url"] == "https://github.com/ada/b"
    plan = store.record(ADA).latest(Kind.PRACTICE_PLAN, "C2")
    assert plan is not None
    assert at == plan.at

    store.save_declaration(ADA, "C2", {})
    assert store.record(ADA).declaration("C2") is None
    other = store.record(ADA).declaration("C3")
    assert other is not None
    assert other[0]["note"] == "other Competency"


def test_the_missed_check_points_now_are_the_latest_ticked_alone_or_with_a_self_assessment(  # noqa: E501
    store: Store,
) -> None:
    assert store.record(ADA).missed_check_points("C1", "redraw") is None
    store.save_missed_check_points(ADA, "C1", "redraw", ["queue"])
    assert store.record(ADA).missed_check_points("C1", "redraw") == ["queue"]

    store.save_self_assessment(
        ADA, "C1", {"levels": {}, "missed_check_points": {"redraw": []}}
    )

    assert store.record(ADA).missed_check_points("C1", "redraw") == []
    assert store.record(ADA).missed_check_points("C1", "other") is None


def test_each_student_has_their_own_record(store: Store) -> None:
    store.open_record(ADA)
    store.open_record(GRACE)
    store.save_answer(ADA, "C1", "guided-calculation", {"sentence": "Ada's"})

    assert store.record(GRACE).entries == ()
    latest = store.record(ADA).latest(Kind.ANSWER, "C1", "guided-calculation")
    assert latest is not None
    assert latest.payload["fields"]["sentence"] == "Ada's"


def test_concurrent_sends_from_many_students_all_land(store: Store) -> None:
    students = [
        Student(2000 + n, f"s{n}", f"Student {n}", "OcéENS", "OcéENS", f"s{n}/OceENS")
        for n in range(12)
    ]

    def path(student: Student) -> None:
        for n in range(4):
            store.save_question(student, "C1", "read-the-chain", f"q{n}")

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(path, students * 2))

    for student in students:
        questions = store.record(student).all(Kind.QUESTION, "C1")
        assert sorted(q.version for q in questions) == list(range(1, 9))
