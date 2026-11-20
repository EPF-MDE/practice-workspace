"""What a reading of a Student's fork returns: facts per Competency, each tied to a
point id.

A reading is plain data, stored as JSON (one file per Student on `workspace-data`) and
rebuilt with `ForkReading.from_dict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.roster import GROUPS

COMPETENCIES = ("C1", "C2", "C3")

# Points no fork can show (#451 points 4 and 5): the panel says "Not visible from your
# fork: show it at the Eval" (C2) or "show your PostHog at the Eval" (C3).
NOT_VISIBLE = {
    "C1": (),
    "C2": ("C2.f", "C2.g"),
    "C3": ("C3.a", "C3.c", "C3.d", "C3.f"),
}

# Points the reading looks for. A point looked for with no fact is "nothing found".
LOOKED_FOR = {
    "C1": ("C1",),
    "C2": ("C2.a", "C2.b", "C2.c", "C2.d", "C2.e"),
    "C3": ("C3.b", "C3.e"),
}

STUDENT = "student"


@dataclass(frozen=True)
class StudentFork:
    """A roster row, as far as the fork reading needs it."""

    login: str
    project: str  # the roster's `project`: "OcéENS" or "MATHutrice"
    fork: str  # "owner/repo"

    @property
    def upstream(self) -> str:
        return GROUPS[self.project].upstream


@dataclass(frozen=True)
class Fact:
    """One thing the fork shows.

    `point`: the point id it supports ("C2.c"), or "C1" for C1's changed files, which
    the workspace does not judge point by point. `credited_to`: "student", or the
    upstream `course-2026*` branch whose code it is (a Fallback Branch or a Worked
    Example). `detail`: the structured data behind `text`, for readers that word it
    themselves.
    """

    point: str
    text: str
    credited_to: str = STUDENT
    link: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompetencyReading:
    competency: str
    facts: list[Fact]
    nothing_found: list[str]  # points looked for, with no fact
    not_visible: list[str]  # points no fork can show

    def facts_for(self, point: str) -> list[Fact]:
        return [f for f in self.facts if f.point == point]


@dataclass(frozen=True)
class ForkReading:
    """A reading of one Student's fork.

    `empty`: no branch and no pull request changes a file beyond the course's code. The
    reading then says where it looked (`branches_read`, `pull_requests_read`), never
    "nothing produced". `read_at`: when the facts were computed. `checked_at`: when the
    fork was last checked for change. `refs`: per ref, its tip SHA and what was computed
    for it, so that a refresh recomputes only the refs that changed.
    """

    student: StudentFork
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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["read_at"] = self.read_at.isoformat()
        d["checked_at"] = self.checked_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ForkReading:
        return cls(
            student=StudentFork(**d["student"]),
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
