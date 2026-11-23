from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.roster import GROUPS, Student

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

STUDENT = "student"

_KEYS_BEFORE_RENAME = {"facts_computed_at": "read_at", "last_checked_at": "checked_at"}


@dataclass(frozen=True)
class StudentToRead:
    login: str
    project: str
    evidence_project: str

    @classmethod
    def from_roster(cls, student: Student) -> StudentToRead:
        return cls(student.github_login, student.project, student.evidence_project)

    @property
    def upstream(self) -> str:
        return GROUPS[self.project].upstream

    @property
    def key(self) -> tuple[str, str]:
        return self.login, self.evidence_project.lower()


def not_read_on_gitlab(repository: str) -> str:
    return (
        f"The workspace cannot read a GitLab project: nothing of `{repository}` is "
        "read here, which says nothing about the work. Show the evidence at the Eval."
    )


@dataclass(frozen=True)
class Fact:
    point: str
    text: str
    credited_to: str = STUDENT
    link: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompetencyReading:
    competency: str
    facts: list[Fact]
    nothing_found: list[str]
    not_visible: list[str]

    def facts_for(self, point: str) -> list[Fact]:
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
            facts_computed_at=_instant(d, "facts_computed_at"),
            last_checked_at=_instant(d, "last_checked_at"),
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


def _instant(d: dict[str, Any], key: str) -> datetime:
    stored = d[key] if key in d else d[_KEYS_BEFORE_RENAME[key]]
    return datetime.fromisoformat(stored)
