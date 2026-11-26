from __future__ import annotations

import threading

from app.roster import Student
from app.store._internal.comments import MARKER_RE, issue_header
from app.store._internal.github_api import GitHubApi

type IssuesByGitHubId = dict[int, list[int]]


class IssueIndex:
    def __init__(self, api: GitHubApi, label: str):
        self._api = api
        self._label = label
        self._index_lock = threading.Lock()
        self._issues: IssuesByGitHubId | None = None

    def issues_of(self, student: Student) -> list[int]:
        with self._index_lock:
            return list(self._loaded().get(student.github_id, ()))

    def owners(self) -> dict[int, int]:
        with self._index_lock:
            return {
                number: github_id
                for github_id, numbers in self._loaded().items()
                for number in numbers
            }

    def issue(self, student: Student) -> int:
        with self._index_lock:
            issues = self._loaded()
            numbers = issues.get(student.github_id)
            if numbers:
                return numbers[0]
            issue = self._api.call(
                "POST",
                "issues",
                json={
                    "title": f"Practice: {student.name} ({student.group})",
                    "body": issue_header(student),
                    "labels": [self._label],
                },
            ).json()
            number: int = issue["number"]
            issues[student.github_id] = [number]
            return number

    def _loaded(self) -> IssuesByGitHubId:
        if self._issues is None:
            found = self._api.all_pages(
                "issues",
                {"labels": self._label, "state": "all"},
            )
            issues: IssuesByGitHubId = {}
            for issue in sorted(found, key=lambda i: i["number"]):
                marker = MARKER_RE.search(issue.get("body") or "")
                if marker and "pull_request" not in issue:
                    issues.setdefault(int(marker[1]), []).append(issue["number"])
            self._issues = issues
        return self._issues
