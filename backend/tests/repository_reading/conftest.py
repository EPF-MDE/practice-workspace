from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.repository_reading import InMemoryReadings, RepositoryReader, StudentToRead
from app.repository_reading.recorded import RecordedGitHub
from app.roster import Repository

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 12, 11, 9, 0, tzinfo=UTC)

OCEENS = Repository("EPF-MDE/OceENS")
MATHUTRICE = Repository("EPF-MDE/MATHutrice")

REPOSITORIES = {
    "empty-repository": StudentToRead(
        "dorothy-math", "MATHutrice", Repository("dorothy-math/MATHutrice"), MATHUTRICE
    ),
    "work-off-default": StudentToRead(
        "rosalind-oceens", "OcéENS", Repository("rosalind-oceens/OceENS"), OCEENS
    ),
    "deleted-pr-branch": StudentToRead(
        "barbara-oceens", "OcéENS", Repository("barbara-oceens/OceENS"), OCEENS
    ),
    "placeholder-email": StudentToRead(
        "frances-oceens", "OcéENS", Repository("frances-oceens/OceENS"), OCEENS
    ),
    "claude-author": StudentToRead(
        "joan-oceens", "OcéENS", Repository("joan-oceens/OceENS"), OCEENS
    ),
    "fallback-default": StudentToRead(
        "radia-oceens", "OcéENS", Repository("radia-oceens/OceENS"), OCEENS
    ),
    "both-environments": StudentToRead(
        "emmy-math", "MATHutrice", Repository("emmy-math/MATHutrice"), MATHUTRICE
    ),
}


class Recorded:
    def __init__(self, name: str) -> None:
        self.student = REPOSITORIES[name]
        self.github = RecordedGitHub.load(FIXTURES / f"{name}.json.gz")
        self.readings = InMemoryReadings()
        self.reader = RepositoryReader(self.github, self.readings, now=lambda: NOW)

    def compares(self) -> list[str]:
        return [p for p in self.github.requests if "/compare/" in p]


@pytest.fixture
def recorded() -> type[Recorded]:
    return Recorded
