"""GitHub's Issues and Contents APIs, faked over HTTP for the GitHub Store's tests.

Only what the Store calls: list a repository's issues by label, open an issue,
list and add an issue's comments, list every issue's comments at once; on a
branch, list a folder, read a file (at the branch or at a commit), and create
or update a file (one commit each, refused with 409 when the file's `sha` is
stale). It answers like api.github.com (status codes, JSON shapes, `Link`
pagination, server timestamps), counts the content-generating requests GitHub's
secondary limit counts, and can be made to fail like GitHub down or
rate-limited.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

REPOSITORY = "EPF-MDE/complex-web-services"
BOT = {"login": "epf-mde-cws-store[bot]", "type": "Bot"}
COMMENT_LIMIT = 65_536  # GitHub refuses a longer comment body with 422


class FakeGitHub:
    def __init__(self, repository: str = REPOSITORY, max_per_page: int = 100):
        self.repository = repository
        self.max_per_page = max_per_page
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.writes = 0  # POST/PATCH/PUT/DELETE answered
        self.reads = 0
        self.down: int | None = None  # a status every request gets, e.g. 503 or 403
        # Branch -> its commits, oldest first: (commit sha, message, {path: bytes}).
        self.branches: dict[str, list[tuple[str, str, dict[str, bytes]]]] = {
            "workspace-data": []
        }
        # The next file writes answer 409, as when another writer moved the branch.
        self.conflicts = 0
        # Issues the label search does not list yet: GitHub's search lags
        # seconds behind a new issue.
        self.unlisted: set[int] = set()
        self._time = datetime(2026, 12, 1, 9, 0, tzinfo=UTC)
        self._lock = threading.Lock()  # the Store sends from several threads

    def client(self) -> httpx.Client:
        """A client as the Store gets in production, its transport this fake."""
        return httpx.Client(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(self.handle),
        )

    # --- what a test may do by hand, as a person on github.com would ---------

    def comment_by_hand(
        self, number: int, body: str, login: str = "the-instructor", type: str = "User"
    ) -> None:
        """A comment by a person, or by another App (`type="Bot"`, e.g.
        `github-actions[bot]`)."""
        with self._lock:
            self._add_comment(number, body, {"login": login, "type": type})

    def commit_by_hand(self, branch: str, path: str, data: bytes) -> None:
        """Another writer (the Repository reading's batch, a person) commits on the
        branch."""
        with self._lock:
            self._commit(branch, path, data, "by hand")

    def files(
        self, branch: str = "workspace-data", at: str | None = None
    ) -> dict[str, bytes]:
        """The branch's files, at its head or at one of its commits."""
        commits = self.branches[branch]
        if at is None:
            return commits[-1][2] if commits else {}
        return next(files for sha, _, files in commits if sha == at)

    def history(self, path: str, branch: str = "workspace-data") -> list[bytes]:
        """Every version of one file, in the order its commits came."""
        versions, last = [], None
        for _, _, files in self.branches[branch]:
            if files.get(path) is not None and files.get(path) != last:
                versions.append(files[path])
            last = files.get(path)
        return versions

    # --- the API -------------------------------------------------------------

    def _tick(self) -> str:
        self._time += timedelta(seconds=1)
        return self._time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def handle(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            return self._handle(request)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(self.down, json={"message": "Service unavailable"})
        if request.method == "GET":
            self.reads += 1
        else:
            self.writes += 1
        contents = f"/repos/{self.repository}/contents/"
        if request.url.path.startswith(contents):
            return self._contents(request, request.url.path[len(contents) :])
        prefix = f"/repos/{self.repository}/issues"
        path = request.url.path
        if not path.startswith(prefix):
            return httpx.Response(404, json={"message": "Not Found"})
        rest = path[len(prefix) :]
        if rest == "/comments" and request.method == "GET":
            return self._page(
                request,
                sorted(
                    (c for cs in self.comments.values() for c in cs),
                    key=lambda c: c["id"],
                ),
            )
        if rest == "" and request.method == "GET":
            return self._list_issues(request)
        if rest == "" and request.method == "POST":
            return self._open_issue(json.loads(request.content))
        match = re.fullmatch(r"/(\d+)/comments", rest)
        if match and int(match[1]) in self.issues:
            number = int(match[1])
            if request.method == "GET":
                return self._page(request, self.comments[number])
            if request.method == "POST":
                body = json.loads(request.content)["body"]
                if len(body) > COMMENT_LIMIT:
                    return httpx.Response(
                        422,
                        json={
                            "message": "Validation Failed",
                            "errors": [{"field": "body"}],
                        },
                    )
                return httpx.Response(201, json=self._add_comment(number, body, BOT))
        return httpx.Response(404, json={"message": "Not Found"})

    def _list_issues(self, request: httpx.Request) -> httpx.Response:
        wanted = set(filter(None, request.url.params.get("labels", "").split(",")))
        state = request.url.params.get("state", "open")
        issues = [
            issue
            for issue in self.issues.values()
            if wanted <= {label["name"] for label in issue["labels"]}
            and state in ("all", issue["state"])
            and issue["number"] not in self.unlisted
        ]
        return self._page(request, sorted(issues, key=lambda i: -i["number"]))

    def _open_issue(self, body: dict[str, Any]) -> httpx.Response:
        number = 1 + max(self.issues, default=400)
        issue = {
            "number": number,
            "title": body["title"],
            "body": body.get("body", ""),
            "labels": [{"name": name} for name in body.get("labels", [])],
            "state": "open",
            "user": BOT,
            "created_at": self._tick(),
            "html_url": f"https://github.com/{self.repository}/issues/{number}",
        }
        self.issues[number] = issue
        self.comments[number] = []
        return httpx.Response(201, json=issue)

    def _add_comment(
        self, number: int, body: str, user: dict[str, str]
    ) -> dict[str, Any]:
        comment = {
            "id": 9000 + sum(len(c) for c in self.comments.values()),
            "body": body,
            "user": user,
            "created_at": self._tick(),
            "html_url": f"https://github.com/{self.repository}/issues/{number}#issuecomment",
            "issue_url": f"https://api.github.com/repos/{self.repository}/issues/{number}",
        }
        self.comments[number].append(comment)
        return comment

    def _page(
        self, request: httpx.Request, items: list[dict[str, Any]]
    ) -> httpx.Response:
        per_page = min(int(request.url.params.get("per_page", 30)), self.max_per_page)
        page = int(request.url.params.get("page", 1))
        headers = {}
        if page * per_page < len(items):
            params = {**dict(request.url.params), "page": page + 1}
            next_url = request.url.copy_with(query=urlencode(params).encode())
            headers["Link"] = f'<{next_url}>; rel="next"'
        return httpx.Response(
            200, json=items[(page - 1) * per_page : page * per_page], headers=headers
        )

    # --- Contents ----------------------------------------------------------------

    @staticmethod
    def _blob_sha(data: bytes) -> str:
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

    def _commit(self, branch: str, path: str, data: bytes, message: str) -> str:
        commits = self.branches.setdefault(branch, [])
        files = {**(commits[-1][2] if commits else {}), path: data}
        sha = hashlib.sha1(
            f"{branch}{len(commits)}{message}".encode() + data
        ).hexdigest()
        commits.append((sha, message, files))
        self._tick()
        return sha

    def _at(self, ref: str) -> dict[str, bytes] | None:
        if ref in self.branches:
            return self.files(ref)
        for commits in self.branches.values():
            for sha, _, files in commits:
                if sha == ref:
                    return files
        return None

    def _contents(self, request: httpx.Request, path: str) -> httpx.Response:
        if request.method == "GET":
            files = self._at(request.url.params.get("ref", "main"))
            if files is None:
                return httpx.Response(
                    404, json={"message": "No commit found for the ref"}
                )
            if path in files:
                data = files[path]
                if "raw" in request.headers.get("accept", ""):
                    return httpx.Response(200, content=data)
                return httpx.Response(
                    200,
                    json={
                        "type": "file",
                        "path": path,
                        "sha": self._blob_sha(data),
                        "size": len(data),
                        "encoding": "base64",
                        "content": base64.b64encode(data).decode()
                        if len(data) < 1_000_000
                        else "",
                    },
                )
            inside = sorted(p for p in files if p.startswith(path.rstrip("/") + "/"))
            if not inside:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(
                200,
                json=[
                    {
                        "type": "file",
                        "path": p,
                        "name": p.rsplit("/", 1)[-1],
                        "sha": self._blob_sha(files[p]),
                    }
                    for p in inside
                    if "/" not in p[len(path.rstrip("/")) + 1 :]
                ],
            )
        if request.method == "PUT":
            body = json.loads(request.content)
            branch = body.get("branch", "main")
            if branch not in self.branches:
                return httpx.Response(404, json={"message": "Branch not found"})
            if self.conflicts:
                self.conflicts -= 1
                return httpx.Response(
                    409, json={"message": f"{branch} is at another commit"}
                )
            current = self.files(branch).get(path)
            if current is not None and body.get("sha") != self._blob_sha(current):
                status = 422 if "sha" not in body else 409
                return httpx.Response(status, json={"message": "sha does not match"})
            data = base64.b64decode(body["content"])
            sha = self._commit(branch, path, data, body["message"])
            return httpx.Response(
                200 if current is not None else 201,
                json={
                    "content": {
                        "path": path,
                        "sha": self._blob_sha(data),
                        "size": len(data),
                    },
                    "commit": {"sha": sha, "message": body["message"]},
                },
            )
        return httpx.Response(405, json={"message": "Method not allowed"})
