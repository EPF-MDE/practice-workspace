"""The batch reading the Instructor runs before each session: every repository on the
roster, one file per Student.

    cd backend
    # reads all repositories, one commit on workspace-data
    uv run python -m app.repository_reading.batch
    # a dry run: the files go to DIR
    uv run python -m app.repository_reading.batch --out DIR
    # repositories read with `gh auth token`
    uv run python -m app.repository_reading.batch --gh-token ...

Settings come from `app.settings` (this repository's `.env`, or the environment).
Repositories are read with the Student Connector App's installation token
(`WORKSPACE_GITHUB_APP_*`), or with `gh auth token` given `--gh-token`. The roster is
read from, and the readings written to, `workspace-data` with the Store App's token
(`WORKSPACE_STORE_APP_*`), unless `--roster` and `--out` are given. About 3,700 requests
for 37 repositories; a repository that fails is named and the others are still written.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.settings import Settings

from .github import HttpGitHub, installation_token, static_token
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


def roster_students(csv_text: str) -> list[StudentToRead]:
    rows = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")))
    return [
        StudentToRead(
            r["github_login"].strip(),
            r["project"].strip(),
            r["evidence_project"].strip(),
        )
        for r in rows
        if r.get("evidence_project")
    ]


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
    args = p.parse_args(argv)
    settings = Settings()

    if args.gh_token:
        token = static_token(
            subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    else:
        token = installation_token(
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
    students = roster_students(roster)
    if args.only:
        wanted = set(args.only.split(","))
        students = [s for s in students if s.login in wanted]

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
    )
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
