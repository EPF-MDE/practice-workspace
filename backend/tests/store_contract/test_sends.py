from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fake_github import FakeGitHub

from app.roster import Repository, Student
from app.store import EVERY_COMPETENCY, MAX_SEND_CHARS, Kind, SendTooLarge, Store

from .conftest import ADA_OF_OCEENS, GRACE_OF_MATHUTRICE, SENDS, declared, github_store


def test_a_record_is_empty_before_any_send(store: Store) -> None:
    assert store.record(ADA_OF_OCEENS).entries == ()


def test_an_answer_is_read_back_as_the_current_state(store: Store) -> None:
    store.save_answer(
        ADA_OF_OCEENS, "C1", "guided-calculation", {"sentence": "D is at most 2 h"}
    )

    latest = store.record(ADA_OF_OCEENS).latest(Kind.ANSWER, "C1", "guided-calculation")

    assert latest is not None
    assert latest.payload == {"fields": {"sentence": "D is at most 2 h"}}
    assert latest.version == 1


def test_each_send_is_a_new_version_and_every_version_is_kept(store: Store) -> None:
    store.save_answer(ADA_OF_OCEENS, "C1", "guided-calculation", {"sentence": "first"})
    store.save_answer(ADA_OF_OCEENS, "C1", "guided-calculation", {"sentence": "second"})
    store.save_answer(ADA_OF_OCEENS, "C1", "the-number-changes", {"what-moves": "D"})

    record = store.record(ADA_OF_OCEENS)

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
    sent = SENDS[kind](store, ADA_OF_OCEENS)

    read = store.record(ADA_OF_OCEENS).latest(kind, sent.competency, sent.key)

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
    store.save_evidence_plan(ADA_OF_OCEENS, "C1", {"text": "kept"})

    with pytest.raises(SendTooLarge):
        store.save_evidence_plan(ADA_OF_OCEENS, "C1", {"text": "x" * MAX_SEND_CHARS})
    with pytest.raises(SendTooLarge):
        store.save_evidence_plan(
            ADA_OF_OCEENS, "C1", {"text": "\n" * (MAX_SEND_CHARS // 2 + 1)}
        )

    assert [e.payload["text"] for e in store.record(ADA_OF_OCEENS).entries] == ["kept"]
    assert (
        store.save_evidence_plan(
            ADA_OF_OCEENS, "C1", {"text": "y" * (MAX_SEND_CHARS - 100)}
        ).version
        == 2
    )


def test_the_largest_send_accepted_fits_one_github_comment(github: FakeGitHub) -> None:
    store = github_store(github)
    text = "é\n" * ((MAX_SEND_CHARS - 100) // 3)

    store.save_question(ADA_OF_OCEENS, "C1", "read-the-chain", text)
    store.save_evidence_plan(
        ADA_OF_OCEENS, "C1", {"text": "y" * (MAX_SEND_CHARS - 100), "confirmed": True}
    )

    assert len(github_store(github).record(ADA_OF_OCEENS).entries) == 2


def test_every_question_is_kept_with_its_step(store: Store) -> None:
    store.save_question(ADA_OF_OCEENS, "C1", "read-the-chain", "First")
    store.save_question(ADA_OF_OCEENS, "C1", "guided-calculation", "Second")
    store.save_question(ADA_OF_OCEENS, "C2", "read-the-chain", "Third")

    questions = store.record(ADA_OF_OCEENS).all(Kind.QUESTION, "C1")

    assert [(q.key, q.payload["text"]) for q in questions] == [
        ("read-the-chain", "First"),
        ("guided-calculation", "Second"),
    ]


def test_an_empty_declaration_withdraws_the_last_one(store: Store) -> None:
    store.save_declaration(ADA_OF_OCEENS, declared("https://github.com/a/b"))
    store.save_declaration(ADA_OF_OCEENS, {})

    latest = store.record(ADA_OF_OCEENS).latest(Kind.DECLARATION, EVERY_COMPETENCY)
    assert latest is not None
    assert latest.payload == {}
    assert store.record(ADA_OF_OCEENS).declaration() is None


def test_a_declaration_stored_with_a_note_reads_back_what_to_read(
    store: Store,
) -> None:
    alone = declared("https://github.com/ada/a")
    alone["note"] = alone.pop("what_to_read")
    store.save_declaration(ADA_OF_OCEENS, alone)
    assert (declaration := store.record(ADA_OF_OCEENS).declaration()) is not None
    assert declaration.what_to_read == "n"

    in_a_plan = declared("https://github.com/ada/b", "the README")
    in_a_plan["note"] = in_a_plan.pop("what_to_read")
    store.save_evidence_plan(
        ADA_OF_OCEENS, "C2", {"text": "p", "declaration": in_a_plan}
    )
    assert (declaration := store.record(ADA_OF_OCEENS).declaration()) is not None
    assert declaration.what_to_read == "the README"


def test_a_declaration_reads_back_what_to_read(store: Store) -> None:
    store.save_declaration(
        ADA_OF_OCEENS, declared("https://github.com/ada/a", "the README")
    )

    declaration = store.record(ADA_OF_OCEENS).declaration()

    assert declaration is not None
    assert declaration.what_to_read == "the README"


def test_one_declaration_per_student_the_latest_sent_alone_or_with_any_closing_step(
    store: Store,
) -> None:
    assert store.record(ADA_OF_OCEENS).declaration() is None
    store.save_declaration(ADA_OF_OCEENS, declared("https://github.com/ada/a", "first"))
    store.save_evidence_plan(
        ADA_OF_OCEENS,
        "C2",
        {"text": "p", "declaration": declared("https://github.com/ada/b", "n")},
    )

    declaration = store.record(ADA_OF_OCEENS).declaration()
    assert declaration is not None
    assert (declaration.url, declaration.repository, declaration.host) == (
        "https://github.com/ada/b",
        "ada/b",
        "github",
    )
    plan = store.record(ADA_OF_OCEENS).latest(Kind.EVIDENCE_PLAN, "C2")
    assert plan is not None
    assert declaration.at == plan.at

    store.save_declaration(ADA_OF_OCEENS, declared("https://github.com/ada/c", "c"))
    changed = store.record(ADA_OF_OCEENS).declaration()
    assert changed is not None
    assert changed.url == "https://github.com/ada/c"
    assert store.record(GRACE_OF_MATHUTRICE).declaration() is None

    store.save_declaration(ADA_OF_OCEENS, {})
    assert store.record(ADA_OF_OCEENS).declaration() is None


def test_several_records_are_read_at_once_each_its_own_students(store: Store) -> None:
    store.save_declaration(ADA_OF_OCEENS, declared("https://github.com/ada/a", "n"))
    store.save_answer(
        GRACE_OF_MATHUTRICE, "C1", "guided-calculation", {"sentence": "Grace's"}
    )
    store.save_declaration(ADA_OF_OCEENS, declared("https://github.com/ada/b", "n"))
    nobody = Student(
        3000, "nobody", "No One", "OcéENS", "OcéENS", Repository("nobody/OceENS")
    )

    ada, grace, none = store.records([ADA_OF_OCEENS, GRACE_OF_MATHUTRICE, nobody])

    assert ada.entries == store.record(ADA_OF_OCEENS).entries
    latest = ada.declaration()
    assert latest is not None
    assert latest.url == "https://github.com/ada/b"
    versions = ada.history(Kind.DECLARATION, EVERY_COMPETENCY)
    assert [e.version for e in versions] == [1, 2]
    assert grace.entries == store.record(GRACE_OF_MATHUTRICE).entries
    assert grace.declaration() is None
    assert none.entries == ()


def test_the_missed_check_points_now_are_the_latest_ticked_alone_or_with_a_self_assessment(  # noqa: E501
    store: Store,
) -> None:
    assert store.record(ADA_OF_OCEENS).missed_check_points("C1", "redraw") is None
    store.save_missed_check_points(ADA_OF_OCEENS, "C1", "redraw", ["queue"])
    assert store.record(ADA_OF_OCEENS).missed_check_points("C1", "redraw") == ["queue"]

    store.save_self_assessment(
        ADA_OF_OCEENS, "C1", {"levels": {}, "missed_check_points": {"redraw": []}}
    )

    assert store.record(ADA_OF_OCEENS).missed_check_points("C1", "redraw") == []
    assert store.record(ADA_OF_OCEENS).missed_check_points("C1", "other") is None


def test_each_student_has_their_own_record(store: Store) -> None:
    store.open_record(ADA_OF_OCEENS)
    store.open_record(GRACE_OF_MATHUTRICE)
    store.save_answer(ADA_OF_OCEENS, "C1", "guided-calculation", {"sentence": "Ada's"})

    assert store.record(GRACE_OF_MATHUTRICE).entries == ()
    latest = store.record(ADA_OF_OCEENS).latest(Kind.ANSWER, "C1", "guided-calculation")
    assert latest is not None
    assert latest.payload["fields"]["sentence"] == "Ada's"


def test_concurrent_sends_from_many_students_all_land(store: Store) -> None:
    students = [
        Student(
            2000 + n,
            f"s{n}",
            f"Student {n}",
            "OcéENS",
            "OcéENS",
            Repository(f"s{n}/OceENS"),
        )
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
