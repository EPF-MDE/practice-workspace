from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.github_app import data_branch_lock, installation_client
from app.roster import Student
from app.settings import Settings
from app.store._internal.comments import (
    _MARKER_RE,
    _entry,
    _header,
    _renumbered,
    _time,
    comment_body,
)
from app.store._internal.model import (
    EVERY_COMPETENCY,
    GITHUB_COMMENT_LIMIT,
    DrawingFiles,
    Entry,
    Record,
    SendTooLarge,
    StoreUnavailable,
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

STORE_BOT = "epf-mde-cws-store[bot]"
PER_PAGE = 100
DATA_RETRIES = 5


class _OnIssue(BaseModel):
    issue_url: str

    @property
    def number(self) -> int:
        return int(self.issue_url.rsplit("/", 1)[-1])


class GitHubStore:
    @classmethod
    def from_settings(cls, settings: Settings) -> GitHubStore:
        client = installation_client(
            settings.store_app_id,
            settings.store_app_private_key_base64,
            settings.store_app_installation_id,
        )
        bot: dict[str, Any] = (
            {"bot_login": f"{settings.store_app_slug}[bot]"}
            if settings.store_app_slug
            else {}
        )
        return cls(
            client,
            settings.repository,
            label=settings.store_label,
            data_branch=settings.data_branch,
            **bot,
        )

    def __init__(
        self,
        http: httpx.Client,
        repository: str,
        label: str = "practice",
        data_branch: str = "workspace-data",
        sleep: Callable[[float], None] = time.sleep,
        bot_login: str = STORE_BOT,
    ):
        self._http = http
        self._repository = repository
        self._label = label
        self._data_branch = data_branch
        self._sleep = sleep
        self._bot_login = bot_login
        self._lock = threading.Lock()
        self._data_lock = data_branch_lock(repository, data_branch)
        self._issues: dict[int, list[int]] | None = None
        self._records: dict[int, list[Entry[Payload]]] = {}
        self._student_locks: dict[int, threading.RLock] = {}
        self._drawings: dict[tuple[int, str, str], DrawingFiles] = {}

    def _call(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            raise StoreUnavailable(f"GitHub did not answer: {error}") from error
        if response.is_error:
            raise StoreUnavailable(
                f"GitHub answered {response.status_code} to {method} {url}"
            )
        return response

    def _all_pages(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response = self._call("GET", url, params={**params, "per_page": PER_PAGE})
        while True:
            items += response.json()
            following = response.links.get("next", {}).get("url")
            if not following:
                return items
            response = self._call("GET", following)

    def _index(self) -> dict[int, list[int]]:
        if self._issues is None:
            issues = self._all_pages(
                f"/repos/{self._repository}/issues",
                {"labels": self._label, "state": "all"},
            )
            index: dict[int, list[int]] = {}
            for issue in sorted(issues, key=lambda i: i["number"]):
                found = _MARKER_RE.search(issue.get("body") or "")
                if found and "pull_request" not in issue:
                    index.setdefault(int(found[1]), []).append(issue["number"])
            self._issues = index
        return self._issues

    def _issues_of(self, student: Student) -> list[int]:
        with self._lock:
            return list(self._index().get(student.github_id, ()))

    def _issue(self, student: Student, create: bool) -> int | None:
        with self._lock:
            numbers = self._index().get(student.github_id)
            number = numbers[0] if numbers else None
            if number is None and create:
                issue = self._call(
                    "POST",
                    f"/repos/{self._repository}/issues",
                    json={
                        "title": f"Practice: {student.name} ({student.group})",
                        "body": _header(student),
                        "labels": [self._label],
                    },
                ).json()
                number = issue["number"]
                self._index()[student.github_id] = [number]
            return number

    def _student_lock(self, student: Student) -> threading.RLock:
        with self._lock:
            return self._student_locks.setdefault(student.github_id, threading.RLock())

    def _entries(self, student: Student) -> list[Entry[Payload]]:
        if student.github_id not in self._records:
            entries: list[Entry[Payload]] = []
            for number in self._issues_of(student):
                comments = self._all_pages(
                    f"/repos/{self._repository}/issues/{number}/comments", {}
                )
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
        self._issue(student, create=True)

    def record(self, student: Student) -> Record:
        with self._student_lock(student):
            return Record(student, tuple(self._entries(student)))

    def records(self, students: list[Student]) -> list[Record]:
        with self._lock:
            owners = {
                number: github_id
                for github_id, numbers in self._index().items()
                for number in numbers
            }
        comments = self._all_pages(f"/repos/{self._repository}/issues/comments", {})
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
        key: str | None,
        payload: P,
    ) -> Entry[P]:
        check_size(payload)
        with self._student_lock(student):
            entries = self._entries(student)
            number = self._issue(student, create=True)
            version = 1 + sum(
                1
                for e in entries
                if (e.kind, e.competency, e.key) == (payload.KIND, competency, key)
            )
            body = comment_body(competency, key, version, payload)
            if len(body) > GITHUB_COMMENT_LIMIT:
                raise SendTooLarge(
                    f"the comment would be {len(body):,} characters, over GitHub's "
                    "limit"
                )
            comment = self._call(
                "POST",
                f"/repos/{self._repository}/issues/{number}/comments",
                json={"body": body},
            ).json()
            entry = Entry(
                competency, key, payload, version, _time(comment["created_at"])
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
            with self._data_lock:
                self._put_file(folder, png_path, png, message)
                commit = self._put_file(folder, snapshot_path, snapshot_bytes, message)
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
                at = latest.payload.commit or self._data_branch
                png = self._raw_file(latest.payload.png, at)
                snapshot = json.loads(self._raw_file(latest.payload.snapshot, at))
                self._drawings[key] = DrawingFiles(png, snapshot)
            return self._drawings[key]

    def _put_file(self, folder: str, path: str, data: bytes, message: str) -> str:
        url = f"/repos/{self._repository}/contents/"
        for attempt in range(DATA_RETRIES):
            body = {
                "message": message,
                "content": base64.b64encode(data).decode(),
                "branch": self._data_branch,
            }
            current = self._file_sha(folder, path)
            if current:
                body["sha"] = current
            try:
                response = self._http.put(url + path, json=body)
            except httpx.HTTPError as error:
                raise StoreUnavailable(f"GitHub did not answer: {error}") from error
            if response.status_code == 409:
                self._sleep(0.5 * (attempt + 1))
                continue
            if response.is_error:
                raise StoreUnavailable(
                    f"GitHub answered {response.status_code} to PUT {path}"
                )
            sha: str = response.json()["commit"]["sha"]
            return sha
        raise StoreUnavailable(f"{self._data_branch} kept moving: {path} not written")

    def _file_sha(self, folder: str, path: str) -> str | None:
        try:
            response = self._http.get(
                f"/repos/{self._repository}/contents/{folder}",
                params={"ref": self._data_branch},
            )
        except httpx.HTTPError as error:
            raise StoreUnavailable(f"GitHub did not answer: {error}") from error
        if response.status_code == 404:
            return None
        if response.is_error:
            raise StoreUnavailable(
                f"GitHub answered {response.status_code} to GET {folder}"
            )
        return next(
            (item["sha"] for item in response.json() if item["path"] == path), None
        )

    def _raw_file(self, path: str, ref: str) -> bytes:
        return self._call(
            "GET",
            f"/repos/{self._repository}/contents/{path}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.raw+json"},
        ).content

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
