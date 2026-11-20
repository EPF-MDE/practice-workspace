"""The GitHub Store's drawings: files on workspace-data, one comment."""

from __future__ import annotations

import json

import pytest
from fake_github import FakeGitHub

from app.store import DrawingFiles, StoreUnavailable

from .conftest import ADA, PNG, SNAPSHOT, github_store


def test_a_drawing_send_is_two_files_on_workspace_data_and_one_comment(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    store.open_record(ADA)
    writes = github.writes

    store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)

    assert github.writes == writes + 3
    files = github.files("workspace-data")
    assert files["drawings/ada-oceens/C1/redraw.png"] == PNG
    assert json.loads(files["drawings/ada-oceens/C1/redraw.snapshot.json"]) == SNAPSHOT
    (comment,) = github.comments[401]
    assert comment["body"].startswith("**Drawing** `redraw` for C1 (version 1)")
    assert "drawings/ada-oceens/C1/redraw.png" in comment["body"]


def test_a_new_version_overwrites_the_same_paths_and_git_history_keeps_every_version(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)
    store.save_drawing(ADA, "C1", "redraw", b"\x89PNG second", SNAPSHOT)

    assert [p for p in github.files() if p.startswith("drawings/")] == [
        "drawings/ada-oceens/C1/redraw.png",
        "drawings/ada-oceens/C1/redraw.snapshot.json",
    ]
    assert github.history("drawings/ada-oceens/C1/redraw.png") == [
        PNG,
        b"\x89PNG second",
    ]


def test_after_a_restart_a_drawing_is_read_from_workspace_data_at_its_version(
    github: FakeGitHub,
) -> None:
    github_store(github).save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)
    github.commit_by_hand(
        "workspace-data", "drawings/ada-oceens/C1/redraw.png", b"overwritten by hand"
    )

    assert github_store(github).drawing(ADA, "C1", "redraw") == DrawingFiles(
        PNG, SNAPSHOT
    )


def test_a_drawing_send_retries_when_another_writer_moved_the_branch(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    github.commit_by_hand(
        "workspace-data", "drawings/ada-oceens/C1/redraw.png", b"an older one"
    )
    github.conflicts = 2

    store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)

    assert github.files()["drawings/ada-oceens/C1/redraw.png"] == PNG


def test_a_branch_that_keeps_moving_makes_the_store_unavailable_and_records_no_version(  # noqa: E501
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    github.conflicts = 100

    with pytest.raises(StoreUnavailable):
        store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)

    assert store.record(ADA).entries == ()
    github.conflicts = 0
    assert store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT).version == 1


def test_github_failing_on_a_drawing_makes_the_store_unavailable(
    github: FakeGitHub,
) -> None:
    store = github_store(github)
    github.down = 502

    with pytest.raises(StoreUnavailable):
        store.save_drawing(ADA, "C1", "redraw", PNG, SNAPSHOT)
