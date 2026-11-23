from __future__ import annotations

from pydantic import BaseModel

from ..github import GitHubError
from ..reading import (
    COMPETENCIES,
    LOOKED_FOR,
    NOT_VISIBLE,
    CompetencyReading,
    RepositoryReading,
)
from .analysis import _Analysis
from .c1 import _C1Facts
from .c2 import _C2Facts
from .c3 import _C3Facts
from .ref_analysis import RefAnalysis
from .rules import (
    _ref_shas,
)


class _Source(BaseModel):
    full_name: str


class _Repository(BaseModel):
    default_branch: str
    source: _Source | None = None


class _Reading(_Analysis, _C1Facts, _C2Facts, _C3Facts):
    def run(self) -> RepositoryReading:
        s = self.s
        repo = self.github.get(f"repos/{s.evidence_project}")
        if repo.status != 200:
            raise GitHubError(f"GET repos/{s.evidence_project}: {repo.status}")
        answer = _Repository.model_validate(repo.body)
        self.default = answer.default_branch
        self.linked_to_upstream = (
            answer.source is not None
            and answer.source.full_name.lower() == s.upstream.lower()
        )
        branch_list, pull_list = self.github.list_refs(s)
        branches_by_name, pulls_by_number = _ref_shas(branch_list, pull_list)
        self.ref_names = {}
        for b in branch_list:
            self.ref_names.setdefault(b["commit"]["sha"], []).append(f"`{b['name']}`")
        for p in pull_list:
            self.ref_names.setdefault(p["head"]["sha"], []).append(
                f"pull request #{p['number']}"
            )
        self.upstream = self.github.upstream_branches(s.upstream)
        reusable = self._reusable_analyses()
        default_sha = branches_by_name.get(self.default)
        self.analyses = {
            sha: self._analysis_of(sha, reusable, sha == default_sha)
            for sha in {*branches_by_name.values(), *pulls_by_number.values()}
        }

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

        now = self.now()
        return RepositoryReading(
            student=s,
            default_branch=self.default,
            facts_computed_at=now,
            last_checked_at=now,
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
                "analyses": {sha: a.to_dict() for sha, a in self.analyses.items()},
            },
            upstream_shas=self.upstream,
        )

    def _reusable_analyses(self) -> dict[str, RefAnalysis]:
        if not self.previous or self.previous.upstream_shas != self.upstream:
            return {}
        stored = self.previous.refs.get("analyses", {})
        return {
            sha: a
            for sha, d in stored.items()
            if (a := RefAnalysis.from_dict(d)) is not None
        }
