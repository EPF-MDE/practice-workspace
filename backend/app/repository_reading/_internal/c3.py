from __future__ import annotations

from typing import Any

from ..reading import (
    Fact,
)
from .rules import (
    FIX_PR,
    POSTHOG_FALLBACK,
    _date,
)
from .state import _ReadingState


class _C3Facts(_ReadingState):
    def _c3b(self, default_sha: str | None) -> None:
        for sha, a in self.analyses.items():
            if a.get("posthog_identity"):
                self.facts["C3"].append(
                    Fact(
                        point="C3.b",
                        text="Your code on "
                        f"{', '.join(self.ref_names.get(sha, [])[:3])} "
                        "sends errors to PostHog with an identity "
                        f"({', '.join(f'`{p}`' for p in a['posthog_files'][:3])}).",
                        link=a.get("link"),
                        detail={"files": a["posthog_files"]},
                    )
                )
                break
        on_default = self.analyses.get(default_sha) if default_sha else None
        if on_default and on_default.get("fallback") == POSTHOG_FALLBACK:
            self.facts["C3"].append(
                Fact(
                    point="C3.b",
                    text=f"`{self.default}` is built on the PostHog Fallback Branch, "
                    "whose code sends errors to PostHog with an identity.",
                    credited_to=POSTHOG_FALLBACK,
                    detail={"fallback": POSTHOG_FALLBACK},
                )
            )

    def _c3e(
        self, pull_list: list[dict[str, Any]], deployments: dict[str, dict[str, Any]]
    ) -> None:
        latest = deployments.get("production")
        if not latest:
            return
        for p in sorted(pull_list, key=lambda p: p["number"]):
            merged, sha = p.get("merged_at"), p.get("merge_commit_sha")
            if not merged or not sha or merged > latest["created_at"]:
                continue
            if not (
                FIX_PR.search(p.get("title") or "") or FIX_PR.search(p["head"]["ref"])
            ):
                continue
            c = (
                self.github.compare(self.s.evidence_project, sha, latest["sha"])
                if sha != latest["sha"]
                else {"behind_by": 0}
            )
            if c is not None and c["behind_by"] == 0:
                self.facts["C3"].append(
                    Fact(
                        point="C3.e",
                        text=f"Pull request #{p['number']} “{p['title']}” "
                        "went through your pipeline to production "
                        f"(deployed on {_date(latest['created_at'])}).",
                        link=p.get("html_url"),
                        detail={
                            "pull_request": p["number"],
                            "deployment_sha": latest["sha"],
                        },
                    )
                )
