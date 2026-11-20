"""Records a fork's GitHub responses as a test fixture (read-only GET requests).

    GH_TOKEN=$(gh auth token) uv run python -m tests.fork_reading.record \
        <login> <project> <owner/repo> <name>

writes tests/fork_reading/fixtures/<name>.json.gz, trimmed to what the reading reads,
and prints the reading's facts and its request count. A recording of a real fork holds
its Student's data: only fictional recordings go in this public repository.
"""

import os
import sys
from pathlib import Path

from app.fork_reading import (
    ForkReader,
    HttpGitHub,
    InMemoryReadings,
    StudentFork,
    static_token,
)
from app.fork_reading.recorded import RecordingGitHub, save_recording

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    login, project, fork, name = sys.argv[1:5]
    github = RecordingGitHub(HttpGitHub(static_token(os.environ["GH_TOKEN"])))
    reading = ForkReader(github, InMemoryReadings()).read_now(
        StudentFork(login, project, fork)
    )
    save_recording(github.recording, FIXTURES / f"{name}.json.gz")
    print(
        f"{len(github.recording)} requests; {reading.branches_read} branches, "
        f"{reading.pull_requests_read} PRs; empty={reading.empty}"
    )
    for c in reading.competencies.values():
        for f in c.facts:
            print(f"  {f.point} [{f.credited_to}] {f.text}")
        print(f"  {c.competency} nothing found: {c.nothing_found}")


if __name__ == "__main__":
    main()
