"""C1's facts: what each branch and pull request changes."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ..reading import (
    Fact,
)

if TYPE_CHECKING:
    pass
from .analysis import OWN_HISTORY
from .rules import (
    _plural,
)
from .state import _ReadingState


class _C1Facts(_ReadingState):
    # --- C1
    # --------------------------------------------------------------------------------

    def _c1(
        self,
        branch_list: list[dict[str, Any]],
        pull_list: list[dict[str, Any]],
        branches_by_name: dict[str, str],
    ) -> None:
        ordered = sorted(
            branch_list, key=lambda b: (b["name"] != self.default, b["name"])
        )
        for b in ordered:
            a = self.analyses[b["commit"]["sha"]]
            if a["files"]:
                self.facts["C1"].append(
                    self._c1_fact(a, f"`{b['name']}`", {"branch": b["name"]})
                )
        branch_shas = set(branches_by_name.values())
        for p in sorted(pull_list, key=lambda p: p["number"]):
            sha = p["head"]["sha"]
            a = self.analyses[sha]
            if not a["files"] or sha in branch_shas:
                continue  # its work is listed under its branch
            deleted = p["head"]["ref"] not in branches_by_name
            where = f"pull request #{p['number']}" + (
                " (its branch was deleted)" if deleted else ""
            )
            fact = self._c1_fact(
                a, where, {"pull_request": p["number"], "branch_deleted": deleted}
            )
            self.facts["C1"].append(replace(fact, link=p.get("html_url") or fact.link))

    def _c1_fact(self, a: dict[str, Any], where: str, ref: dict[str, Any]) -> Fact:
        n = len(a["files"])
        text = (
            f"{where} holds {_plural(n, 'file')} of its own history, none from the "
            f"course's code; last change on {a['last_change']}."
            if a.get(OWN_HISTORY)
            else f"{where} changes {_plural(n, 'file')} beyond `{a['closest']}`, "
            f"{_plural(a['lines_added'], 'line')} added; "
            f"last change on {a['last_change']}."
        )
        return Fact(
            point="C1",
            text=text,
            link=a.get("link"),
            detail={
                **ref,
                "closest": a["closest"],
                "files": a["files"],
                "lines_added": a["lines_added"],
                "last_change": a["last_change"],
            },
        )
