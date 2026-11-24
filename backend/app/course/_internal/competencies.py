from __future__ import annotations

from collections.abc import Callable

COMPETENCIES = ("C1", "C2", "C3")


def competency_problems(
    ids: set[str], missing: Callable[[str], str], unknown: Callable[[str], str]
) -> list[str]:
    return [missing(c) for c in COMPETENCIES if c not in ids] + [
        unknown(c) for c in sorted(ids - set(COMPETENCIES))
    ]
