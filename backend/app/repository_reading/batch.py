"""The batch reading the Instructor runs before each session: every Student's Evidence
Project, one file per Student.

    cd backend
    # reads all repositories, one commit on workspace-data
    uv run python -m app.repository_reading.batch
    # a dry run: the files go to DIR
    uv run python -m app.repository_reading.batch --out DIR
    # repositories read with `gh auth token`
    uv run python -m app.repository_reading.batch --gh-token ...
    # the roster's Evidence Projects only, without reading the Store
    uv run python -m app.repository_reading.batch --roster-only ...

Settings come from `app.settings` (this repository's `.env`, or the environment).
Repositories are read with the Student Connector App's installation on each one, else
its installation `WORKSPACE_GITHUB_APP_INSTALLATION_ID` (`WORKSPACE_GITHUB_APP_*`), or
with `gh auth token` given `--gh-token`. The roster is read from, and the readings
written to, `workspace-data` with the Store App's token (`WORKSPACE_STORE_APP_*`),
unless `--roster` and `--out` are given. Each Student's Evidence Project is the GitHub
repository they declared, read from the Store with the Store App's token, else the
roster's; a GitLab project is named, not read. About 3,700 requests for 37
repositories; a repository that fails is named and the others are still written.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.roster import Student, parse_roster
from app.settings import Settings
from app.store import GitHubStore, Store

from .github import (
    HttpGitHub,
    TokenFor,
    installation_token,
    repository_tokens,
    static_token,
)
from .reader import RepositoryReader
from .reading import RepositoryReading, StudentToRead
from .storage import (
    DirectoryReadings,
    GitHubWorkspaceData,
    InMemoryReadings,
    WorkspaceData,
    encode,
    reading_path,
)


def evidence_projects(
    students: list[Student], store: Store
) -> tuple[list[StudentToRead], dict[str, str]]:
    """Each Student's Evidence Project as the Reading Day reads it: the one declared,
    else the roster's; and the GitLab projects, which cannot be read here, by login."""
    to_read: list[StudentToRead] = []
    gitlab: dict[str, str] = {}
    for student, record in zip(students, store.records(students), strict=True):
        declared = record.declaration()
        repository = declared[0]["repository"] if declared else student.evidence_project
        if declared and declared[0]["host"] == "gitlab":
            gitlab[student.github_login] = repository
            continue
        to_read.append(StudentToRead(student.github_login, student.project, repository))
    return to_read, gitlab


def _roster_project(student: Student) -> StudentToRead:
    return StudentToRead(
        student.github_login, student.project, student.evidence_project
    )


@dataclass
class BatchResult:
    readings: dict[str, RepositoryReading] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


def _silent(line: str) -> None:
    pass


def read_all(
    students: list[StudentToRead],
    reader: RepositoryReader,
    log: Callable[[str], None] = _silent,
) -> BatchResult:
    result = BatchResult()
    for s in students:
        try:
            reading = reader.read_now(s)
        except Exception as e:  # one repository failing must not lose the others
            result.failures[s.login] = f"{type(e).__name__}: {e}"
            log(f"{s.login}: FAILED {result.failures[s.login]}")
            continue
        result.readings[s.login] = reading
        log(
            f"{s.login}: {reading.branches_read} branches, "
            f"{reading.pull_requests_read} pull requests, "
            f"{sum(len(c.facts) for c in reading.competencies.values())} facts"
        )
    return result


def run_batch(
    students: list[StudentToRead],
    reader: RepositoryReader,
    data: WorkspaceData,
    log: Callable[[str], None] = _silent,
) -> BatchResult:
    """Reads every repository, then writes one file per Student in a single commit."""
    result = read_all(students, reader, log)
    if result.readings:
        data.write(
            {reading_path(login): encode(r) for login, r in result.readings.items()},
            f"data: batch reading of {len(result.readings)} repositories",
        )
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--roster", type=Path, help="a local roster.csv instead of workspace-data's"
    )
    p.add_argument(
        "--out",
        type=Path,
        help="write the files to this folder instead of workspace-data",
    )
    p.add_argument(
        "--gh-token",
        action="store_true",
        help="read the repositories with `gh auth token`",
    )
    p.add_argument("--only", help="comma-separated logins")
    p.add_argument(
        "--roster-only",
        action="store_true",
        help="read the roster's Evidence Projects, not the Store's declarations",
    )
    args = p.parse_args(argv)
    settings = Settings()

    if args.gh_token:
        token: TokenFor = static_token(
            subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    else:
        token = repository_tokens(
            settings.github_app_id,
            settings.github_app_private_key_base64,
            settings.github_app_installation_id,
        )
    store = None
    if not (args.roster and args.out):
        store = GitHubWorkspaceData(
            settings.repository,
            installation_token(
                settings.store_app_id,
                settings.store_app_private_key_base64,
                settings.store_app_installation_id,
            ),
            branch=settings.data_branch,
        )

    if args.roster:
        roster = args.roster.read_text(encoding="utf-8")
    else:
        assert store is not None
        raw = store.read("roster.csv")
        assert raw is not None
        roster = raw.decode("utf-8")
    roster_rows = list(parse_roster(roster))
    if args.only:
        wanted = set(args.only.split(","))
        roster_rows = [s for s in roster_rows if s.github_login in wanted]
    gitlab: dict[str, str] = {}
    if args.roster_only:
        students = [_roster_project(s) for s in roster_rows]
    else:
        students, gitlab = evidence_projects(
            roster_rows, GitHubStore.from_settings(settings)
        )

    github = HttpGitHub(token)
    reader = RepositoryReader(github, InMemoryReadings())

    def log(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    if args.out:
        result = read_all(students, reader, log)
        out = DirectoryReadings(args.out)
        for login, reading in result.readings.items():
            out.save(login, reading)
    else:
        assert store is not None
        result = run_batch(students, reader, store, log)
    print(
        f"{len(result.readings)} repositories read, {len(result.failures)} failed"
        + "".join(f"\n  {k}: {v}" for k, v in result.failures.items())
        + "".join(
            f"\n  {k}: GitLab project {v}, not read: show it at the Eval"
            for k, v in gitlab.items()
        )
    )
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
