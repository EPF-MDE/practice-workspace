from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.repository_reading import InMemoryReadings, RepositoryReader, StudentToRead
from app.repository_reading.recorded import RecordedGitHub
from app.roster import Repository

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 12, 11, 9, 0, tzinfo=UTC)

WILLOW = Repository("example-course/lendly")
CEDAR = Repository("example-course/skywatch")

REPOSITORIES = {
    "empty-repository": StudentToRead(
        "dorothy-cedar", "Cedar", Repository("dorothy-cedar/skywatch"), CEDAR
    ),
    "work-off-default": StudentToRead(
        "rosalind-willow", "Willow", Repository("rosalind-willow/lendly"), WILLOW
    ),
    "deleted-pr-branch": StudentToRead(
        "barbara-willow", "Willow", Repository("barbara-willow/lendly"), WILLOW
    ),
    "placeholder-email": StudentToRead(
        "frances-willow", "Willow", Repository("frances-willow/lendly"), WILLOW
    ),
    "claude-author": StudentToRead(
        "joan-willow", "Willow", Repository("joan-willow/lendly"), WILLOW
    ),
    "fallback-default": StudentToRead(
        "radia-willow", "Willow", Repository("radia-willow/lendly"), WILLOW
    ),
    "both-environments": StudentToRead(
        "emmy-cedar", "Cedar", Repository("emmy-cedar/skywatch"), CEDAR
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
