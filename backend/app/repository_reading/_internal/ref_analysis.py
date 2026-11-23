from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError

from ..reading import ChangedFile

WORKFLOWS_FOLDER = ".github/workflows/"


class HowRead(StrEnum):
    AGAINST_UPSTREAM = "against_upstream"
    OWN_HISTORY = "own_history"
    UNREADABLE = "unreadable"


class Workflow(BaseModel, frozen=True):
    architecture: bool = False
    deploy_needs: dict[str, list[str]] = {}


class RefAnalysis(BaseModel, frozen=True):
    read: HowRead
    files: tuple[ChangedFile, ...] = ()
    closest: str | None = None
    lines_added: int | None = None
    last_change: str | None = None
    link: str | None = None
    posthog_identity: bool = False
    posthog_files: tuple[str, ...] = ()
    changed_workflows: dict[str, Workflow] = {}
    default_branch_workflows: dict[str, Workflow] = {}
    read_as_default_branch: bool = False
    fallback: str | None = None

    @property
    def changed_paths(self) -> set[str]:
        return {f.path for f in self.files}

    @property
    def workflow_paths(self) -> list[str]:
        return [f.path for f in self.files if f.path.startswith(WORKFLOWS_FOLDER)]

    @property
    def workflows(self) -> dict[str, Workflow]:
        return {**self.default_branch_workflows, **self.changed_workflows}

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, stored: Any) -> RefAnalysis | None:
        try:
            return cls.model_validate(stored)
        except ValidationError:
            return None


UNREADABLE = RefAnalysis(read=HowRead.UNREADABLE)
