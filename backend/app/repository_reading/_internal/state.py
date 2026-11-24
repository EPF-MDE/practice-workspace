from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import yaml

from app.course import COMPETENCIES

from ..reading import (
    Fact,
    RepositoryReading,
    StudentToRead,
)
from .cached_github import _CachedGitHub
from .ref_analysis import RefAnalysis, Workflow


class _ReadingState:
    default: str
    linked_to_upstream: bool
    ref_names: dict[str, list[str]]
    upstream: dict[str, str]
    analyses: dict[str, RefAnalysis]

    def __init__(
        self,
        github: _CachedGitHub,
        now: Callable[[], datetime],
        student: StudentToRead,
        previous: RepositoryReading | None,
    ):
        self.github = github
        self.now = now
        self.s = student
        self.previous = previous
        self.facts: dict[str, list[Fact]] = {c: [] for c in COMPETENCIES}

    def _workflow(self, sha: str, path: str) -> Workflow | None:
        text = self.github.file_at(self.s.evidence_project, sha, path)
        if text is None:
            return None
        try:
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            return Workflow()
        jobs = doc.get("jobs") or {} if isinstance(doc, dict) else {}
        architecture = False
        deploy_needs: dict[str, list[str]] = {}
        for job_id, job in jobs.items():
            job = job if isinstance(job, dict) else {}
            if job_id == "architecture" or job.get("name") == "architecture":
                architecture = True
            if "deploy" in str(job_id).lower():
                needs = job.get("needs") or []
                deploy_needs[job_id] = (
                    [needs] if isinstance(needs, str) else list(needs)
                )
        return Workflow(architecture=architecture, deploy_needs=deploy_needs)

    def _all_workflows(self, sha: str) -> dict[str, Workflow]:
        r = self.github.get(
            f"repos/{self.s.evidence_project}/contents/.github/workflows?ref={sha}"
        )
        if r.status != 200 or not isinstance(r.body, list):
            return {}
        out = {}
        for entry in r.body:
            if entry.get("type") == "file" and entry["name"].endswith(
                (".yml", ".yaml")
            ):
                w = self._workflow(sha, entry["path"])
                if w is not None:
                    out[entry["path"]] = w
        return out
