from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, NewType

from pydantic import BaseModel

from app.roster import GROUPS, Repository, Student

COMPETENCIES = ("C1", "C2", "C3")


class PointId(StrEnum):
    CHANGED_FILES = "C1"
    C2_A = "C2.a"
    C2_B = "C2.b"
    C2_C = "C2.c"
    C2_D = "C2.d"
    C2_E = "C2.e"
    C2_F = "C2.f"
    C2_G = "C2.g"
    C3_A = "C3.a"
    C3_B = "C3.b"
    C3_C = "C3.c"
    C3_D = "C3.d"
    C3_E = "C3.e"
    C3_F = "C3.f"


NOT_VISIBLE: dict[str, tuple[PointId, ...]] = {
    "C1": (),
    "C2": (PointId.C2_F, PointId.C2_G),
    "C3": (PointId.C3_A, PointId.C3_C, PointId.C3_D, PointId.C3_F),
}

LOOKED_FOR: dict[str, tuple[PointId, ...]] = {
    "C1": (PointId.CHANGED_FILES,),
    "C2": (PointId.C2_A, PointId.C2_B, PointId.C2_C, PointId.C2_D, PointId.C2_E),
    "C3": (PointId.C3_B, PointId.C3_E),
}

Credit = NewType("Credit", str)

STUDENT = Credit("student")


class ChangedFile(BaseModel):
    path: str
    additions: int | None = None
    changes: int | None = None


_KEYS_BEFORE_RENAME = {"facts_computed_at": "read_at", "last_checked_at": "checked_at"}


@dataclass(frozen=True)
class StudentToRead:
    login: str
    project: str
    evidence_project: Repository

    @classmethod
    def from_roster(cls, student: Student) -> StudentToRead:
        return cls(student.github_login, student.project, student.evidence_project)

    @property
    def upstream(self) -> Repository:
        return GROUPS[self.project].upstream

    @property
    def key(self) -> tuple[str, str]:
        return self.login, self.evidence_project.lower()


def not_read_on_gitlab(repository: Repository) -> str:
    return (
        f"The workspace cannot read a GitLab project: nothing of `{repository}` is "
        "read here, which says nothing about the work. Show the evidence at the Eval."
    )


@dataclass(frozen=True)
class Fact:
    point: PointId
    text: str
    credited_to: Credit = STUDENT
    link: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompetencyReading:
    competency: str
    facts: list[Fact]
    nothing_found: list[PointId]
    not_visible: list[PointId]

    def facts_for(self, point: PointId) -> list[Fact]:
        return [f for f in self.facts if f.point == point]


@dataclass(frozen=True)
class RepositoryReading:
    student: StudentToRead
    default_branch: str
    facts_computed_at: datetime
    last_checked_at: datetime
    branches_read: int
    pull_requests_read: int
    empty: bool
    competencies: dict[str, CompetencyReading]
    refs: dict[str, dict[str, Any]] = field(default_factory=dict)
    upstream_shas: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, competency: str) -> CompetencyReading:
        return self.competencies[competency]

    def reads(self, student: StudentToRead) -> bool:
        return self.student.key == student.key

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["facts_computed_at"] = self.facts_computed_at.isoformat()
        d["last_checked_at"] = self.last_checked_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RepositoryReading:
        return cls(
            student=StudentToRead(**d["student"]),
            default_branch=d["default_branch"],
            facts_computed_at=_stored_instant(d, "facts_computed_at"),
            last_checked_at=_stored_instant(d, "last_checked_at"),
            branches_read=d["branches_read"],
            pull_requests_read=d["pull_requests_read"],
            empty=d["empty"],
            competencies={
                k: CompetencyReading(
                    competency=c["competency"],
                    facts=[
                        Fact(**{**f, "point": PointId(f["point"])}) for f in c["facts"]
                    ],
                    nothing_found=[PointId(p) for p in c["nothing_found"]],
                    not_visible=[PointId(p) for p in c["not_visible"]],
                )
                for k, c in d["competencies"].items()
            },
            refs=d.get("refs", {}),
            upstream_shas=d.get("upstream_shas", {}),
        )


def _stored_instant(d: dict[str, Any], key: str) -> datetime:
    stored = d[key] if key in d else d[_KEYS_BEFORE_RENAME[key]]
    return datetime.fromisoformat(stored)
