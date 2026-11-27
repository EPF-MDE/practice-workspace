from __future__ import annotations

from ..reading import Credit
from .rules import FALLBACK_CHAIN

_FALLBACK_NAMES = dict(
    zip(
        FALLBACK_CHAIN,
        (
            "the course's starting code",
            "the Clean Bench Fallback Branch",
            "the CI Fallback Branch",
            "the Ready-to-Deploy Fallback Branch",
            "the PostHog Fallback Branch",
        ),
        strict=True,
    )
)


def branch_name(credit: Credit) -> str:
    return _FALLBACK_NAMES.get(credit, f"the course's branch `{credit}`")
