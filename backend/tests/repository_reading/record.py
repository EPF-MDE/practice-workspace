"""Records a repository's GitHub responses as a test fixture (read-only GET requests).

    GH_TOKEN=$(gh auth token) uv run python -m tests.repository_reading.record \
        <login> <project> <owner/repo> <name>

writes tests/repository_reading/fixtures/<name>.json.gz, trimmed to what the reading
reads, and prints the reading's facts and its request count. A recording of a real
repository holds its Student's data: only fictional recordings go in this public
repository.
"""

import os
import sys
from pathlib import Path

from app.repository_reading import (
    HttpGitHub,
    InMemoryReadings,
    RepositoryReader,
    StudentRepository,
    static_token,
)
from app.repository_reading.recorded import RecordingGitHub, save_recording

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    login, project, repository, name = sys.argv[1:5]
    github = RecordingGitHub(HttpGitHub(static_token(os.environ["GH_TOKEN"])))
    reading = RepositoryReader(github, InMemoryReadings()).read_now(
        StudentRepository(login, project, repository)
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
