from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fake_github import FakeGitHub

from app.roster import Repository, Student
from app.store import (
    DeclarationPayload,
    Entry,
    EvidencePlanPayload,
    GitHubStore,
    InMemoryStore,
    Kind,
    Payload,
    PointLevelPayload,
    SelfAssessmentPayload,
    Store,
)

ADA_OF_OCEENS = Student(
    1001, "ada-oceens", "Ada Lovelace", "OcéENS", Repository("ada-oceens/OceENS")
)
GRACE_OF_MATHUTRICE = Student(
    1002,
    "grace-math",
    "Grace Hopper",
    "MATHutrice",
    Repository("grace-math/MATHutrice"),
)


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


def github_store(github: FakeGitHub, label: str = "practice") -> GitHubStore:
    return GitHubStore(
        github.client(), github.repository, label=label, sleep=lambda seconds: None
    )


@pytest.fixture(params=["memory", "github"])
def store(request: pytest.FixtureRequest, github: FakeGitHub) -> Store:
    if request.param == "memory":
        return InMemoryStore()
    return github_store(github)


def declared(url: str, what_to_read: str = "n") -> DeclarationPayload:
    host, repository = url.removeprefix("https://").split(".com/")
    return DeclarationPayload.model_validate(
        {
            "url": url,
            "what_to_read": what_to_read,
            "repository_path": repository,
            "host": host,
            "access_when_declared": "gitlab" if host == "gitlab" else "readable",
        }
    )


SENDS: dict[Kind, Callable[[Store, Student], Entry[Payload]]] = {
    Kind.ANSWER: lambda s, who: s.send_answer(
        who, "C1", "guided-calculation", {"sentence": "D ≤ 2 h", "unit": "h"}
    ),
    Kind.CHECK_POINTS: lambda s, who: s.send_missed_check_points(
        who, "C2", "redraw", ["queue", "retry"]
    ),
    Kind.SELF_ASSESSMENT: lambda s, who: s.send_self_assessment(
        who,
        "C1",
        SelfAssessmentPayload(
            levels={
                "C1.a": PointLevelPayload(
                    level="done", link="https://github.com/x/y/pull/3"
                ),
                "C1.b": PointLevelPayload(level="redo", link=None),
            },
            missed_check_points={"redraw": ["queue"]},
        ),
    ),
    Kind.EVIDENCE_PLAN: lambda s, who: s.send_evidence_plan(
        who,
        "C1",
        EvidencePlanPayload(
            text="Redo the gate\n\nC1.b, été",
            example="my README",
            confirmed=True,
            declaration=declared("https://github.com/ada/bakery", "été"),
            evidence_panel_snapshot={
                "competency": "C1",
                "facts": [{"point": "C1", "files": []}],
                "files_dropped": True,
            },
        ),
    ),
    Kind.DECLARATION: lambda s, who: s.send_declaration(
        who, declared("https://gitlab.com/a/b", "été")
    ),
    Kind.QUESTION: lambda s, who: s.send_question(
        who, "C1", "read-the-chain", "Why 10?\nAnd why ``` here?"
    ),
    Kind.EVIDENCE_PANEL_SNAPSHOT: lambda s, who: s.send_evidence_panel_snapshot(
        who, "C2", {"empty": False, "facts": [{"point": "C2.c"}]}
    ),
}

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
SNAPSHOT: dict[str, Any] = {
    "document": {
        "store": {"shape:a": {"id": "shape:a", "props": {"text": "Côté file"}}},
        "schema": {},
    }
}
