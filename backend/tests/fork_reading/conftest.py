from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.fork_reading import ForkReader, InMemoryReadings, StudentFork
from app.fork_reading.recorded import RecordedGitHub

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 12, 11, 9, 0, tzinfo=UTC)

# Fictional recordings, shaped on forks recorded on 19 November 2026: their logins,
# branches, pull requests, commits and code are invented; their shapes, dates and
# counts are kept. By the shape of #451 each one shows.
FORKS = {
    "empty-fork": StudentFork("dorothy-math", "MATHutrice", "dorothy-math/MATHutrice"),
    "work-off-default": StudentFork(
        "rosalind-oceens", "OcéENS", "rosalind-oceens/OceENS"
    ),
    "deleted-pr-branch": StudentFork(
        "barbara-oceens", "OcéENS", "barbara-oceens/OceENS"
    ),
    "placeholder-email": StudentFork(
        "frances-oceens", "OcéENS", "frances-oceens/OceENS"
    ),
    "claude-author": StudentFork("joan-oceens", "OcéENS", "joan-oceens/OceENS"),
    "fallback-default": StudentFork("radia-oceens", "OcéENS", "radia-oceens/OceENS"),
    "both-environments": StudentFork("emmy-math", "MATHutrice", "emmy-math/MATHutrice"),
}


class Recorded:
    def __init__(self, name: str) -> None:
        self.student = FORKS[name]
        self.github = RecordedGitHub.load(FIXTURES / f"{name}.json.gz")
        self.readings = InMemoryReadings()
        self.reader = ForkReader(self.github, self.readings, now=lambda: NOW)

    def compares(self) -> list[str]:
        return [p for p in self.github.requests if "/compare/" in p]


@pytest.fixture
def recorded() -> type[Recorded]:
    return Recorded
