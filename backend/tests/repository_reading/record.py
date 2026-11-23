import os
import sys
from pathlib import Path

from app.repository_reading import (
    HttpGitHub,
    InMemoryReadings,
    RepositoryReader,
    StudentToRead,
    static_token,
)
from app.repository_reading.recorded import RecordingGitHub, save_recording
from app.roster import Repository

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    login, project, evidence_project, upstream, name = sys.argv[1:6]
    github = RecordingGitHub(HttpGitHub(static_token(os.environ["GH_TOKEN"])))
    reading = RepositoryReader(github, InMemoryReadings()).read_now(
        StudentToRead(
            login, project, Repository(evidence_project), Repository(upstream)
        )
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
