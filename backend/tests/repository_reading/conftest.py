from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.repository_reading import InMemoryReadings, RepositoryReader, StudentToRead
from app.repository_reading.recorded import RecordedGitHub
from app.roster import Repository

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 12, 11, 9, 0, tzinfo=UTC)

REPOSITORIES = {
    "empty-repository": StudentToRead(
        "dorothy-math", "MATHutrice", Repository("dorothy-math/MATHutrice")
    ),
    "work-off-default": StudentToRead(
        "rosalind-oceens", "OcéENS", Repository("rosalind-oceens/OceENS")
    ),
    "deleted-pr-branch": StudentToRead(
        "barbara-oceens", "OcéENS", Repository("barbara-oceens/OceENS")
    ),
    "placeholder-email": StudentToRead(
        "frances-oceens", "OcéENS", Repository("frances-oceens/OceENS")
    ),
    "claude-author": StudentToRead(
        "joan-oceens", "OcéENS", Repository("joan-oceens/OceENS")
    ),
    "fallback-default": StudentToRead(
        "radia-oceens", "OcéENS", Repository("radia-oceens/OceENS")
    ),
    "both-environments": StudentToRead(
        "emmy-math", "MATHutrice", Repository("emmy-math/MATHutrice")
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
