from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.repository_reading import (
    ChangedFile,
    Credit,
    Fact,
    PointId,
    RepositoryReading,
)
from app.repository_reading.reading import not_read_on_gitlab
from app.roster import Repository
from app.store import GITLAB, Host

NOT_VISIBLE = "Not visible from your Evidence Project: show it at the Eval"
NOT_VISIBLE_C3 = "Not visible from your Evidence Project: show your PostHog at the Eval"
C1_NOT_JUDGED = (
    "These are the files you changed beyond the course's code, per branch and pull "
    "request. "
    "The workspace does not judge them: at the Eval, you explain what they do and why."
)
UNAVAILABLE = (
    "Your Evidence Project could not be read just now. "
    "This says nothing about your work: the Reading Day will read it. "
    "Press Refresh later."
)
NOTICE = (
    "The Instructor and an AI tool (Mistral, which may train on what it reads) will "
    "read the project you declare. "
    "If you cannot agree to that, keep your Evidence Project instead."
)
PASSWORD_EXAMPLE = (
    "Evidence behind a password cannot be read on the Reading Day: for example an app "
    "deployed behind a login, "
    "a dashboard on your employer's network, or a document shared only inside a "
    "company. "
    "Put what shows it in the repository instead: screenshots, an export, the steps to "
    "see it."
)
DOCUMENTATION_ADVICE = (
    "Keep the documentation of your evidence in the repository itself (its README, or "
    "a docs folder) "
    "and say in your note which branch, folder, pull request or file to read."
)
SNAPSHOT_MAX_CHARS = 40_000


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _looked(branches: int, pulls: int) -> str:
    return (
        f"{_count(branches, 'branch', 'branches')}, "
        f"{_count(pulls, 'pull request', 'pull requests')}"
    )


def empty_text(branches: int, pulls: int) -> str:
    return (
        "On your Evidence Project, no branch or pull request changes a file "
        "beyond the course's code "
        f"({_looked(branches, pulls)} read). "
        "What to do next: push your work to any branch of your Evidence Project, "
        "or open a pull request, then press Refresh; "
        "or change your Evidence Project in a closing step. "
        "This is a provisional reading, not a zero."
    )


def not_read_text(declaration: Declaration) -> str:
    if declaration.host == GITLAB:
        return not_read_on_gitlab(declaration.repository)
    return (
        f"The course GitHub App cannot read `{declaration.repository}` yet: nothing of "
        "it shows here, which is not a zero. Grant read-only access, or show your "
        "evidence at the Eval."
    )


class PanelFact(BaseModel):
    point: PointId
    text: str
    credited_to: Credit
    link: str | None
    files: list[ChangedFile] = []


class NotVisible(BaseModel):
    point: PointId
    text: str


AccessStatus = Literal["readable", "not-readable", "gitlab"]
READABLE_ACCESS: AccessStatus = "readable"
NOT_READABLE_ACCESS: AccessStatus = "not-readable"
GITLAB_ACCESS: AccessStatus = "gitlab"


class Access(BaseModel):
    status: AccessStatus
    message: str
    how_to_make_readable: str | None


class Declaration(BaseModel):
    url: str
    what_to_read: str
    repository: Repository
    host: Host
    declares_roster_evidence_project: bool
    declared_at: datetime
    access: Access


class DeclarationHelp(BaseModel):
    notice: str = NOTICE
    password_example: str = PASSWORD_EXAMPLE
    documentation_advice: str = DOCUMENTATION_ADVICE


class EvidencePanel(BaseModel):
    competency: str
    evidence_project: Repository
    unavailable: str | None
    facts_computed_at: datetime | None
    last_checked_at: datetime | None
    default_branch: str | None
    branches_read: int
    pull_requests_read: int
    empty: bool
    empty_text: str | None
    facts: list[PanelFact]
    nothing_found: list[PointId]
    nothing_found_text: str | None
    not_visible: list[NotVisible]
    not_judged: str | None
    declaration: Declaration | None
    help: DeclarationHelp


def _fact(fact: Fact) -> PanelFact:
    files = fact.detail.get("files") if fact.point == PointId.CHANGED_FILES else None
    return PanelFact(
        point=fact.point,
        text=fact.text,
        credited_to=fact.credited_to,
        link=fact.link,
        files=[ChangedFile.model_validate(f) for f in files if isinstance(f, dict)]
        if isinstance(files, list)
        else [],
    )


def build_panel(
    competency: str, reading: RepositoryReading, declaration: Declaration | None
) -> EvidencePanel:
    found = reading[competency]
    nothing = [p for p in found.nothing_found if p != PointId.CHANGED_FILES]
    looked = _looked(reading.branches_read, reading.pull_requests_read)
    return EvidencePanel(
        competency=competency,
        evidence_project=reading.student.evidence_project,
        unavailable=None,
        facts_computed_at=reading.facts_computed_at,
        last_checked_at=reading.last_checked_at,
        default_branch=reading.default_branch,
        branches_read=reading.branches_read,
        pull_requests_read=reading.pull_requests_read,
        empty=reading.empty,
        empty_text=empty_text(reading.branches_read, reading.pull_requests_read)
        if reading.empty
        else None,
        facts=[_fact(f) for f in found.facts],
        nothing_found=list(found.nothing_found),
        nothing_found_text=(
            f"Looked for on your Evidence Project ({looked} read), "
            "nothing found yet: "
            f"{', '.join(nothing)}."
            if nothing
            else None
        ),
        not_visible=[
            NotVisible(
                point=p, text=NOT_VISIBLE_C3 if competency == "C3" else NOT_VISIBLE
            )
            for p in found.not_visible
        ],
        not_judged=C1_NOT_JUDGED if competency == "C1" else None,
        declaration=declaration,
        help=DeclarationHelp(),
    )


def unavailable_panel(
    competency: str,
    evidence_project: Repository,
    declaration: Declaration | None,
    unavailable: str = UNAVAILABLE,
) -> EvidencePanel:
    return EvidencePanel(
        competency=competency,
        evidence_project=evidence_project,
        unavailable=unavailable,
        facts_computed_at=None,
        last_checked_at=None,
        default_branch=None,
        branches_read=0,
        pull_requests_read=0,
        empty=False,
        empty_text=None,
        facts=[],
        nothing_found=[],
        nothing_found_text=None,
        not_visible=[],
        not_judged=None,
        declaration=declaration,
        help=DeclarationHelp(),
    )


def snapshot(panel: EvidencePanel) -> dict[str, Any]:
    data = panel.model_dump(mode="json", exclude={"help"})
    if len(json.dumps(data, ensure_ascii=False)) > SNAPSHOT_MAX_CHARS:
        for fact in data["facts"]:
            fact["files"] = []
        data["files_dropped"] = True
    return data
