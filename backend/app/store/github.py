from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.github_app import installation_client
from app.roster import Student
from app.settings import Settings
from app.store._internal.comments import (
    _entry,
    _renumbered,
    _time,
    comment_body,
)
from app.store._internal.data_branch import DataBranch
from app.store._internal.github_api import GitHubApi
from app.store._internal.issue_index import IssueIndex
from app.store._internal.model import (
    EVERY_COMPETENCY,
    GITHUB_COMMENT_LIMIT,
    DrawingFiles,
    Entry,
    Record,
    SendTooLarge,
    check_size,
    drawing_paths,
    drawing_payload,
    snapshot_file,
)
from app.store._internal.payloads import (
    AnswerPayload,
    CheckPointsPayload,
    DeclarationPayload,
    DrawingPayload,
    EvidencePanelSnapshotPayload,
    EvidencePlanPayload,
    Payload,
    QuestionPayload,
    SelfAssessmentPayload,
    WithdrawalPayload,
)


class _OnIssue(BaseModel):
    issue_url: str

    @property
    def number(self) -> int:
        return int(self.issue_url.rsplit("/", 1)[-1])


class GitHubStore:
    @classmethod
    def from_settings(cls, settings: Settings) -> GitHubStore:
        settings.require("The GitHub Store", "repository", "store_app_slug")
        client = installation_client(
            settings.store_app_id,
            settings.store_app_private_key_base64,
            settings.store_app_installation_id,
        )
        return cls(
            client,
            settings.repository,
            settings.store_app_slug,
            label=settings.store_label,
            data_branch=settings.data_branch,
        )

    def __init__(
        self,
        http: httpx.Client,
        repository: str,
        store_app_slug: str,
        label: str = "practice",
        data_branch: str = "workspace-data",
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api = GitHubApi(http, repository)
        self._issues = IssueIndex(self._api, label)
        self._data_branch = DataBranch(self._api, data_branch, sleep)
        self._bot_login = f"{store_app_slug}[bot]"
        self._student_locks_lock = threading.Lock()
        self._records: dict[int, list[Entry[Payload]]] = {}
        self._student_locks: dict[int, threading.RLock] = {}
        self._drawings: dict[tuple[int, str, str], DrawingFiles] = {}

    def _student_lock(self, student: Student) -> threading.RLock:
        with self._student_locks_lock:
            return self._student_locks.setdefault(student.github_id, threading.RLock())

    def _entries(self, student: Student) -> list[Entry[Payload]]:
        with self._student_lock(student):
            if student.github_id not in self._records:
                entries: list[Entry[Payload]] = []
                for number in self._issues.issues_of(student):
                    comments = self._api.all_pages(f"issues/{number}/comments", {})
                    entries += [
                        e
                        for e in (_entry(c, self._bot_login) for c in comments)
                        if e is not None
                    ]
                self._records[student.github_id] = _renumbered(
                    sorted(entries, key=lambda e: e.at)
                )
            return self._records[student.github_id]

    def open_record(self, student: Student) -> None:
        self._issues.issue(student, create=True)

    def record(self, student: Student) -> Record:
        with self._student_lock(student):
            return Record(student, tuple(self._entries(student)))

    def records(self, students: list[Student]) -> list[Record]:
        owners = self._issues.owners()
        comments = self._api.all_pages("issues/comments", {})
        found: dict[int, list[Entry[Payload]]] = {}
        for comment in comments:
            number = _OnIssue.model_validate(comment).number
            entry = _entry(comment, self._bot_login)
            if entry is not None and number in owners:
                found.setdefault(owners[number], []).append(entry)
        return [
            Record(
                student,
                tuple(
                    _renumbered(
                        sorted(found.get(student.github_id, []), key=lambda e: e.at)
                    )
                ),
            )
            for student in students
        ]

    def _append[P: Payload](
        self,
        student: Student,
        competency: str | None,
        step_or_drawing: str | None,
        payload: P,
    ) -> Entry[P]:
        check_size(payload)
        with self._student_lock(student):
            entries = self._entries(student)
            number = self._issues.issue(student, create=True)
            version = 1 + sum(
                1
                for e in entries
                if e.series == (payload.KIND, competency, step_or_drawing)
            )
            body = comment_body(competency, step_or_drawing, version, payload)
            if len(body) > GITHUB_COMMENT_LIMIT:
                raise SendTooLarge(
                    f"the comment would be {len(body):,} characters, over GitHub's "
                    "limit"
                )
            comment = self._api.call(
                "POST",
                f"issues/{number}/comments",
                json={"body": body},
            ).json()
            entry = Entry(
                competency,
                step_or_drawing,
                payload,
                version,
                _time(comment["created_at"]),
            )
            entries.append(entry)
            return entry

    def send_answer(
        self, student: Student, competency: str, step: str, fields: dict[str, str]
    ) -> Entry[AnswerPayload]:
        return self._append(student, competency, step, AnswerPayload(fields=fields))

    def send_drawing(
        self,
        student: Student,
        competency: str,
        drawing: str,
        png: bytes,
        snapshot: dict[str, Any],
    ) -> Entry[DrawingPayload]:
        snapshot_bytes = snapshot_file(snapshot)
        png_path, snapshot_path = drawing_paths(student, competency, drawing)
        with self._student_lock(student):
            version = 1 + len(
                Record(student, tuple(self._entries(student))).history(
                    DrawingPayload, competency, drawing
                )
            )
            message = (
                f"drawing: {student.github_login} {competency} {drawing} "
                f"(version {version})"
            )
            folder = png_path.rsplit("/", 1)[0]
            commit = self._data_branch.write(
                folder, {png_path: png, snapshot_path: snapshot_bytes}, message
            )
            payload = drawing_payload(
                student, competency, drawing, png, snapshot_bytes, commit
            )
            entry = self._append(student, competency, drawing, payload)
            self._drawings[(student.github_id, competency, drawing)] = DrawingFiles(
                png, snapshot
            )
            return entry

    def drawing(
        self, student: Student, competency: str, drawing: str
    ) -> DrawingFiles | None:
        with self._student_lock(student):
            key = (student.github_id, competency, drawing)
            if key not in self._drawings:
                latest = Record(student, tuple(self._entries(student))).latest(
                    DrawingPayload, competency, drawing
                )
                if latest is None:
                    return None
                at = latest.payload.commit or self._data_branch.branch
                png = self._data_branch.read(latest.payload.png, at)
                snapshot = json.loads(
                    self._data_branch.read(latest.payload.snapshot, at)
                )
                self._drawings[key] = DrawingFiles(png, snapshot)
            return self._drawings[key]

    def send_missed_check_points(
        self, student: Student, competency: str, drawing: str, missed: list[str]
    ) -> Entry[CheckPointsPayload]:
        return self._append(
            student, competency, drawing, CheckPointsPayload(missed=missed)
        )

    def send_self_assessment(
        self, student: Student, competency: str, assessment: SelfAssessmentPayload
    ) -> Entry[SelfAssessmentPayload]:
        return self._append(student, competency, None, assessment)

    def send_evidence_plan(
        self, student: Student, competency: str, plan: EvidencePlanPayload
    ) -> Entry[EvidencePlanPayload]:
        return self._append(student, competency, None, plan)

    def send_declaration(
        self, student: Student, declaration: DeclarationPayload
    ) -> Entry[DeclarationPayload]:
        return self._append(student, EVERY_COMPETENCY, None, declaration)

    def withdraw_declaration(self, student: Student) -> Entry[WithdrawalPayload]:
        return self._append(student, EVERY_COMPETENCY, None, WithdrawalPayload())

    def send_question(
        self, student: Student, competency: str, step: str, text: str
    ) -> Entry[QuestionPayload]:
        return self._append(student, competency, step, QuestionPayload(text=text))

    def send_evidence_panel_snapshot(
        self, student: Student, competency: str, snapshot: dict[str, Any]
    ) -> Entry[EvidencePanelSnapshotPayload]:
        return self._append(
            student,
            competency,
            None,
            EvidencePanelSnapshotPayload.model_validate(snapshot),
        )
