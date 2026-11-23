from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, NewType

from pydantic import BaseModel

from app.roster import GROUPS, Repository, Student

COMPETENCIES = ("C1", "C2", "C3")

NOT_VISIBLE = {
    "C1": (),
    "C2": ("C2.f", "C2.g"),
    "C3": ("C3.a", "C3.c", "C3.d", "C3.f"),
}

LOOKED_FOR = {
    "C1": ("C1",),
    "C2": ("C2.a", "C2.b", "C2.c", "C2.d", "C2.e"),
    "C3": ("C3.b", "C3.e"),
}

Point = NewType("Point", str)
Credit = NewType("Credit", str)

CHANGED_FILES = Point("C1")
STUDENT = Credit("student")


class ChangedFile(BaseModel):
    path: str
    additions: int | None = None
    changes: int | None = None


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
    point: Point
    text: str
    credited_to: Credit = STUDENT
    link: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompetencyReading:
    competency: str
    facts: list[Fact]
    nothing_found: list[str]
    not_visible: list[str]

    def facts_for(self, point: Point) -> list[Fact]:
        return [f for f in self.facts if f.point == point]


@dataclass(frozen=True)
class RepositoryReading:
    student: StudentToRead
    default_branch: str
    read_at: datetime
    checked_at: datetime
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
        d["read_at"] = self.read_at.isoformat()
        d["checked_at"] = self.checked_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RepositoryReading:
        return cls(
            student=StudentToRead(**d["student"]),
            default_branch=d["default_branch"],
            read_at=datetime.fromisoformat(d["read_at"]),
            checked_at=datetime.fromisoformat(d["checked_at"]),
            branches_read=d["branches_read"],
            pull_requests_read=d["pull_requests_read"],
            empty=d["empty"],
            competencies={
                k: CompetencyReading(
                    competency=c["competency"],
                    facts=[Fact(**f) for f in c["facts"]],
                    nothing_found=list(c["nothing_found"]),
                    not_visible=list(c["not_visible"]),
                )
                for k, c in d["competencies"].items()
            },
            refs=d.get("refs", {}),
            upstream_shas=d.get("upstream_shas", {}),
        )
