import csv
import io
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pytest

from app.course import Course, load_course
from app.repository_reading import StudentToRead
from app.roster import Repository, Roster, parse_roster

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class OnTheRoster:
    github_id: int
    github_login: str
    name: str
    group: str
    evidence_project: str | None
    block: str
    upstream: str | None

    def marked(self, what: str) -> str:
        return f"{self.block.upper()}-{what}"

    def check_point(self, n: int) -> str:
        return f"{self.block}-{n}"

    def to_read(self, evidence_project: str | None = None) -> StudentToRead:
        to_read = evidence_project or self.evidence_project
        if to_read is None:
            raise ValueError(f"{self.github_login} has no Evidence Project to read")
        return StudentToRead(self.github_login, self.group, Repository(to_read))


@dataclass(frozen=True)
class CourseFolder:
    label: str
    folder: Path

    @cached_property
    def course(self) -> Course:
        course = load_course(self.folder).course
        assert course is not None
        return course

    @property
    def name(self) -> str:
        return self.course.name

    @property
    def roster_file(self) -> Path:
        return self.folder / "roster.csv"

    @property
    def roster_csv(self) -> str:
        return self.roster_file.read_text(encoding="utf-8")

    def roster(self, csv_text: str) -> Roster:
        return parse_roster(
            csv_text, self.course.groups, self.course.roster_names_evidence_projects
        )

    @cached_property
    def students(self) -> list[OnTheRoster]:
        return [
            OnTheRoster(
                int(row["github_id"]),
                row["github_login"],
                row["name"],
                row["group"],
                row.get("evidence_project"),
                self.course.groups[row["group"]].block,
                self.course.groups[row["group"]].upstream,
            )
            for row in csv.DictReader(io.StringIO(self.roster_csv))
        ]

    @property
    def student(self) -> OnTheRoster:
        return self.students[0]

    @property
    def another(self) -> OnTheRoster:
        return self.students[1]

    @property
    def one_per_group(self) -> list[OnTheRoster]:
        firsts = {s.group: s for s in reversed(self.students)}
        return [firsts[group] for group in self.course.groups]

    def others_marked(self, student: OnTheRoster, what: str) -> list[str]:
        return [s.marked(what) for s in self.one_per_group if s.group != student.group]


TWO_GROUP_FIXTURE = CourseFolder("two-Group fixture", FIXTURES / "content")
ONE_GROUP_FIXTURE = CourseFolder(
    "one-Group fixture", FIXTURES / "courses" / "one-group"
)
DEMO_COURSE = CourseFolder(
    "Demo course", Path(__file__).resolve().parents[2] / "demo-course"
)
NOTHING_BY_DEFAULT_FIXTURE = CourseFolder(
    "fixture reading nothing by default", FIXTURES / "courses" / "nothing-by-default"
)
EVERY_FIXTURE = [TWO_GROUP_FIXTURE, ONE_GROUP_FIXTURE]

on_the_two_group_fixture = pytest.mark.parametrize(
    "course", [TWO_GROUP_FIXTURE], ids=["two-Group fixture"], indirect=True
)
