from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from ..reading import ChangedFile
from .ref_analysis import UNREADABLE, HowRead, RefAnalysis
from .rules import (
    FALLBACK_CHAIN,
    IDENTITY,
    LOCKFILES,
    POSTHOG,
    _date,
)
from .state import _ReadingState


class _TreeEntry(BaseModel):
    path: str
    type: str


class _Tree(BaseModel):
    tree: list[_TreeEntry]


class _Committer(BaseModel):
    date: str


class _Commit(BaseModel):
    committer: _Committer


class _Analysis(_ReadingState):
    def _analysis_of(
        self, sha: str, reusable: dict[str, RefAnalysis], on_default_branch: bool
    ) -> RefAnalysis:
        a = reusable.get(sha) or self._analyse(sha)
        if on_default_branch and not a.read_as_default_branch:
            a = a.model_copy(
                update={
                    "read_as_default_branch": True,
                    "fallback": self._fallback_on(sha),
                    "workflows": {**self._all_workflows(sha), **a.workflows},
                }
            )
        unread = {
            path: w
            for path in a.workflow_paths
            if path not in a.workflows and (w := self._workflow(sha, path))
        }
        if unread:
            a = a.model_copy(update={"workflows": {**a.workflows, **unread}})
        return a

    def _analyse(self, sha: str) -> RefAnalysis:
        if sha in self.upstream.values():
            return RefAnalysis(read=HowRead.AGAINST_UPSTREAM)
        comparisons = {}
        for name, usha in self.upstream.items():
            c = self.github.compare(self.s.evidence_project, usha, sha)
            if c is not None:
                comparisons[name] = c
        if not comparisons:
            return UNREADABLE if self.linked_to_upstream else self._own_history(sha)
        if any(c["ahead_by"] == 0 for c in comparisons.values()):
            return RefAnalysis(read=HowRead.AGAINST_UPSTREAM)

        def counted(c: dict[str, Any]) -> dict[str, dict[str, Any]]:
            return {
                f["filename"]: f
                for f in c.get("files", [])
                if f["filename"].rsplit("/", 1)[-1] not in LOCKFILES
            }

        per = {n: counted(c) for n, c in comparisons.items()}
        closest = min(
            per, key=lambda n: (sum(f["changes"] for f in per[n].values()), n)
        )
        files = []
        for path, _f in sorted(per[closest].items()):
            best = min(
                (per[n].get(path) for n in per),
                key=lambda g: -1 if g is None else g["changes"],
            )
            if best is None or best["changes"] == 0:
                continue
            files.append(
                {
                    "path": path,
                    "additions": best["additions"],
                    "changes": best["changes"],
                    "patch": best.get("patch") or "",
                }
            )
        c = comparisons[closest]
        added = [
            line
            for f in files
            for line in f["patch"].splitlines()
            if line.startswith("+")
        ]
        return RefAnalysis(
            read=HowRead.AGAINST_UPSTREAM,
            closest=closest,
            files=tuple(
                ChangedFile(
                    path=f["path"], additions=f["additions"], changes=f["changes"]
                )
                for f in files
            ),
            lines_added=sum(f["additions"] for f in files),
            last_change=self._last_change(c, sha, self.upstream[closest]),
            link=c.get("html_url"),
            posthog_identity=any(POSTHOG.search(line) for line in added)
            and any(IDENTITY.search(line) for line in added),
            posthog_files=tuple(
                f["path"] for f in files if IDENTITY.search(f["patch"])
            ),
        )

    def _own_history(self, sha: str) -> RefAnalysis:
        repo = self.s.evidence_project
        tree = self.github.get(f"repos/{repo}/git/trees/{sha}?recursive=1")
        commit = self.github.get(f"repos/{repo}/git/commits/{sha}")
        if tree.status != 200 or commit.status != 200:
            return UNREADABLE
        paths = sorted(
            e.path
            for e in _Tree.model_validate(tree.body).tree
            if e.type == "blob" and e.path.rsplit("/", 1)[-1] not in LOCKFILES
        )
        committed = _Commit.model_validate(commit.body).committer.date
        return RefAnalysis(
            read=HowRead.OWN_HISTORY,
            files=tuple(ChangedFile(path=path) for path in paths),
            last_change=_date(committed),
            link=f"https://github.com/{repo}/tree/{sha}",
        )

    def _last_change(self, c: dict[str, Any], sha: str, base: str) -> str | None:
        commits = c.get("commits", [])
        if c.get("ahead_by", 0) > len(commits):
            last_page = math.ceil(c["ahead_by"] / 100)
            r = self.github.get(
                f"repos/{self.s.evidence_project}/compare/{base}...{sha}?per_page=100&page={last_page}"
            )
            if r.status == 200:
                commits = r.body.get("commits", []) or commits
        if not commits:
            return None
        return _date(commits[-1]["commit"]["committer"]["date"])

    def _fallback_on(self, sha: str) -> str | None:
        for i in range(len(FALLBACK_CHAIN) - 1, 0, -1):
            name, parent = FALLBACK_CHAIN[i], FALLBACK_CHAIN[i - 1]
            if name not in self.upstream or parent not in self.upstream:
                continue
            c = self.github.compare(self.s.evidence_project, self.upstream[name], sha)
            if c is None:
                continue
            if c["behind_by"] == 0:
                return name
            mb = (c.get("merge_base_commit") or {}).get("sha")
            if not mb:
                continue
            p = self.github.compare(self.s.upstream, self.upstream[parent], mb)
            if p is not None and p["ahead_by"] > 0:
                return name
        return None
