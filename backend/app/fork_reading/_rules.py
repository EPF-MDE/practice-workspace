"""The rules a reading follows: the upstream branches it compares with, and what it
looks for in the files and pull requests of a fork."""

from __future__ import annotations

import re
from typing import Any

COURSE_PREFIX = "course-2026"
LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "bun.lockb",
}

# Each Fallback Branch is built on the one before it
# (assets/course-2026-branches/course-2026-branches.mmd), and a parent is merged forward
# into its child.
FALLBACK_CHAIN = (
    "course-2026",
    "course-2026-fallback-clean-bench",
    "course-2026-fallback-ci",
    "course-2026-fallback-ready-to-deploy",
    "course-2026-fallback-posthog",
)
CLEAN_BENCH = "course-2026-fallback-clean-bench"
POSTHOG_FALLBACK = "course-2026-fallback-posthog"

FIX_PR = re.compile(r"fix|correct|corrig|bug|repair|répar", re.I)
POSTHOG = re.compile(r"posthog", re.I)
IDENTITY = re.compile(r"identify|distinct_id", re.I)
RUNS_PAGES = 3
UPSTREAM_TTL = 15 * 60


def _date(iso: str | None) -> str | None:
    return iso[:10] if iso else None


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _ref_shas(
    branches: list[dict[str, Any]], pulls: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {b["name"]: b["commit"]["sha"] for b in branches},
        {str(p["number"]): p["head"]["sha"] for p in pulls},
    )
