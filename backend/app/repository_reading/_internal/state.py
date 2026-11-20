"""What one reading of a repository holds while it runs, and the workflow files it
reads, for every rule."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from ..reading import (
    COMPETENCIES,
    Fact,
    RepositoryReading,
    StudentToRead,
)

if TYPE_CHECKING:
    from ..reader import RepositoryReader


class _ReadingState:
    """One full reading of one repository: its state, shared by the rules."""

    default: str
    linked_to_upstream: bool  # GitHub links the repository to the Group's upstream
    ref_names: dict[str, list[str]]
    upstream: dict[str, str]
    analyses: dict[str, dict[str, Any]]

    def __init__(
        self,
        reader: RepositoryReader,
        student: StudentToRead,
        previous: RepositoryReading | None,
    ):
        self.r = reader
        self.s = student
        self.previous = previous
        self.facts: dict[str, list[Fact]] = {c: [] for c in COMPETENCIES}

    def _workflow(self, sha: str, path: str) -> dict[str, Any] | None:
        text = self.r.file_at(self.s.evidence_project, sha, path)
        if text is None:
            return None
        try:
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            return {"unparsed": True}
        jobs = doc.get("jobs") or {} if isinstance(doc, dict) else {}
        out: dict[str, Any] = {"architecture": False, "deploy_needs": {}}
        for job_id, job in jobs.items():
            job = job if isinstance(job, dict) else {}
            if job_id == "architecture" or job.get("name") == "architecture":
                out["architecture"] = True
            if "deploy" in str(job_id).lower():
                needs = job.get("needs") or []
                out["deploy_needs"][job_id] = (
                    [needs] if isinstance(needs, str) else list(needs)
                )
        return out

    def _all_workflows(self, sha: str) -> dict[str, dict[str, Any]]:
        r = self.r.github.get(
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
