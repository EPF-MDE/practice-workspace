from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.roster import Student
from app.store import DrawingFiles, Kind, Store

from .conftest import ADA_OF_OCEENS, PNG, SNAPSHOT


def test_a_drawing_is_none_before_it_is_sent(store: Store) -> None:
    assert store.drawing(ADA_OF_OCEENS, "C1", "redraw") is None


def test_a_drawing_reads_back_as_sent_with_its_paths_and_sizes(store: Store) -> None:
    entry = store.save_drawing(ADA_OF_OCEENS, "C1", "redraw", PNG, SNAPSHOT)

    files = store.drawing(ADA_OF_OCEENS, "C1", "redraw")
    assert files is not None
    assert (files.png, files.snapshot) == (PNG, SNAPSHOT)
    latest = store.record(ADA_OF_OCEENS).latest(Kind.DRAWING, "C1", "redraw")
    assert latest is not None
    assert latest == entry and latest.version == 1
    assert latest.payload["png"] == "drawings/ada-oceens/C1/redraw.png"
    assert latest.payload["snapshot"] == "drawings/ada-oceens/C1/redraw.snapshot.json"
    assert latest.payload["png_bytes"] == len(PNG)
    assert latest.payload["snapshot_bytes"] > 0


def test_a_new_drawing_version_replaces_the_files_and_the_record_keeps_both(
    store: Store,
) -> None:
    store.save_drawing(ADA_OF_OCEENS, "C1", "redraw", PNG, SNAPSHOT)
    second: dict[str, Any] = {"document": {"store": {}, "schema": {}}}

    entry = store.save_drawing(ADA_OF_OCEENS, "C1", "redraw", b"\x89PNG second", second)

    assert entry.version == 2
    assert store.drawing(ADA_OF_OCEENS, "C1", "redraw") == DrawingFiles(
        b"\x89PNG second", second
    )
    assert [
        e.version
        for e in store.record(ADA_OF_OCEENS).history(Kind.DRAWING, "C1", "redraw")
    ] == [1, 2]
    assert store.drawing(ADA_OF_OCEENS, "C1", "other") is None


def test_concurrent_drawing_sends_from_many_students_all_land(store: Store) -> None:
    students = [
        Student(3000 + n, f"d{n}", f"Student {n}", "OcéENS", "OcéENS", f"d{n}/OceENS")
        for n in range(19)
    ]

    def send(student: Student) -> None:
        store.save_drawing(
            student, "C1", "redraw", PNG + student.github_login.encode(), SNAPSHOT
        )

    with ThreadPoolExecutor(19) as pool:
        list(pool.map(send, students * 2))

    for student in students:
        files = store.drawing(student, "C1", "redraw")
        assert files is not None
        assert files.png == PNG + student.github_login.encode()
        assert [
            e.version
            for e in store.record(student).history(Kind.DRAWING, "C1", "redraw")
        ] == [1, 2]
