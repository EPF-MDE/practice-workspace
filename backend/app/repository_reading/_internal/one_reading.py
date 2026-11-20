"""One full reading of one repository, from its rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ..github import GitHubError
from ..reading import (
    COMPETENCIES,
    LOOKED_FOR,
    NOT_VISIBLE,
    CompetencyReading,
    RepositoryReading,
)

if TYPE_CHECKING:
    pass
from .analysis import _Analysis
from .c1 import _C1Facts
from .c2 import _C2Facts
from .c3 import _C3Facts
from .rules import (
    _ref_shas,
)


class _Source(BaseModel):
    full_name: str


class _Repository(BaseModel):
    """What the reading needs of GitHub's answer for the repository: `source` is the
    repository GitHub links it to, absent if none."""

    default_branch: str
    source: _Source | None = None


class _Reading(_Analysis, _C1Facts, _C2Facts, _C3Facts):
    """One full reading of one repository."""

    def run(self) -> RepositoryReading:
        s, r = self.s, self.r
        repo = r.github.get(f"repos/{s.evidence_project}")
        if repo.status != 200:
            raise GitHubError(f"GET repos/{s.evidence_project}: {repo.status}")
        answer = _Repository.model_validate(repo.body)
        self.default = answer.default_branch
        self.linked_to_upstream = (
            answer.source is not None
            and answer.source.full_name.lower() == s.upstream.lower()
        )
        branch_list, pull_list = r._list_refs(s)
        branches_by_name, pulls_by_number = _ref_shas(branch_list, pull_list)
        self.ref_names = {}
        for b in branch_list:
            self.ref_names.setdefault(b["commit"]["sha"], []).append(f"`{b['name']}`")
        for p in pull_list:
            self.ref_names.setdefault(p["head"]["sha"], []).append(
                f"pull request #{p['number']}"
            )
        self.upstream = r.upstream_branches(s.upstream)
        reusable = {}
        if self.previous and self.previous.upstream_shas == self.upstream:
            reusable = self.previous.refs.get("analyses", {})
        self.analyses = {}
        default_sha = branches_by_name.get(self.default)
        for sha in {*branches_by_name.values(), *pulls_by_number.values()}:
            a = reusable.get(sha) or self._analyse(sha)
            if sha == default_sha and "fallback" not in a:
                a = {
                    **a,
                    "fallback": self._fallback_on(sha),
                    "workflows": self._all_workflows(sha),
                }
            self.analyses[sha] = a

        self._c1(branch_list, pull_list, branches_by_name)
        runs = self._runs()
        deployments = self._deployments()
        self._c2a(pull_list, runs)
        self._c2b(default_sha)
        self._c2c(branch_list)
        self._c2d(runs)
        self._c2e(deployments)
        self._c3b(default_sha)
        self._c3e(pull_list, deployments)

        now = r.now()
        return RepositoryReading(
            student=s,
            default_branch=self.default,
            read_at=now,
            checked_at=now,
            branches_read=len(branch_list),
            pull_requests_read=len(pull_list),
            empty=not self.facts["C1"],
            competencies={
                c: CompetencyReading(
                    competency=c,
                    facts=self.facts[c],
                    nothing_found=[
                        p
                        for p in LOOKED_FOR[c]
                        if not any(f.point == p for f in self.facts[c])
                    ],
                    not_visible=list(NOT_VISIBLE[c]),
                )
                for c in COMPETENCIES
            },
            refs={
                "branches": branches_by_name,
                "pulls": pulls_by_number,
                "analyses": self.analyses,
            },
            upstream_shas=self.upstream,
        )
