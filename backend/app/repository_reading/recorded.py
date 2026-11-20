"""Recorded GitHub responses: replayed in tests, recorded from real repositories by
`record`.

A recording maps each request path to its response, trimmed to the fields the repository
reading reads (`trim`), so that fixtures hold no names, emails or code beyond what a
test needs.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Any, overload

from .github import GitHub, Response


class Unrecorded(KeyError):
    pass


class RecordedGitHub:
    """Replays a recording. Counts every request, so tests can check the cost."""

    def __init__(self, recording: dict[str, dict[str, Any]]) -> None:
        self.recording = recording
        self.requests: list[str] = []

    @classmethod
    def load(cls, *paths: Path) -> RecordedGitHub:
        recording: dict[str, dict[str, Any]] = {}
        for p in paths:
            recording.update(load_recording(p))
        return cls(recording)

    def get(self, path: str) -> Response:
        self.requests.append(path)
        if path not in self.recording:
            raise Unrecorded(path)
        r = self.recording[path]
        return Response(r["status"], r["body"], r.get("next_page"))

    def set(
        self, path: str, status: int, body: Any, next_page: str | None = None
    ) -> None:
        self.recording[path] = {"status": status, "body": body, "next_page": next_page}


def load_recording(path: Path) -> dict[str, dict[str, Any]]:
    raw = (
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )
    recording: dict[str, dict[str, Any]] = json.loads(raw)
    return recording


def save_recording(recording: dict[str, dict[str, Any]], path: Path) -> None:
    data = json.dumps(
        recording, indent=None, sort_keys=True, ensure_ascii=False
    ).encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


class RecordingGitHub:
    """Passes each request to `inner` and keeps its trimmed response."""

    def __init__(self, inner: GitHub) -> None:
        self.inner = inner
        self.recording: dict[str, dict[str, Any]] = {}

    def get(self, path: str) -> Response:
        r = self.inner.get(path)
        body = trim(path, r.body)
        self.recording[path] = {
            "status": r.status,
            "body": body,
            "next_page": r.next_page,
        }
        return Response(r.status, body, r.next_page)


# --- Trimming: keep only what the reading reads
# --------------------------------------------

_KEEP_PATCH = re.compile(r"posthog|identify|distinct_id", re.I)
_KEEP_EMAIL = re.compile(r"claude|anthropic|exemple|example|noreply", re.I)


@overload
def _pick(d: dict[str, Any], *keys: str) -> dict[str, Any]: ...
@overload
def _pick(d: None, *keys: str) -> None: ...
def _pick(d: dict[str, Any] | None, *keys: str) -> dict[str, Any] | None:
    if d is None:
        return None
    return {k: d.get(k) for k in keys if k in d}


def _trim_commit(c: dict[str, Any]) -> dict[str, Any]:
    author = (c.get("commit") or {}).get("author") or {}
    email = author.get("email") or ""
    return {
        "sha": c.get("sha"),
        "author": _pick(c.get("author"), "login"),
        "commit": {
            "author": {
                "date": author.get("date"),
                **({"email": email} if _KEEP_EMAIL.search(email) else {}),
            },
            "committer": _pick((c.get("commit") or {}).get("committer"), "date"),
        },
    }


def _trim_file(f: dict[str, Any]) -> dict[str, Any]:
    out = _pick(
        f,
        "filename",
        "status",
        "additions",
        "deletions",
        "changes",
        "previous_filename",
    )
    patch = f.get("patch")
    if patch is not None:
        out["patch"] = "\n".join(
            line
            for line in patch.splitlines()
            if line.startswith("+") and _KEEP_PATCH.search(line)
        )
    return out


def trim(path: str, body: Any) -> Any:
    route = path.split("?", 1)[0]
    if not isinstance(body, (dict, list)):
        return body
    return _trim_body(route, body)


def _trim_body(route: str, body: Any) -> Any:
    if isinstance(body, dict) and "message" in body and len(body) <= 3:
        return _pick(body, "message")
    if re.search(r"/compare/", route):
        return {
            **_pick(
                body, "status", "ahead_by", "behind_by", "total_commits", "html_url"
            ),
            "merge_base_commit": _pick(body.get("merge_base_commit"), "sha"),
            "commits": [_trim_commit(c) for c in body.get("commits", [])],
            "files": [_trim_file(f) for f in body.get("files", [])],
        }
    if re.search(r"/branches$", route):
        return [
            {
                "name": b["name"],
                "commit": {"sha": b["commit"]["sha"]},
                "protected": b.get("protected"),
            }
            for b in body
        ]
    if re.search(r"^repos/[^/]+/[^/]+/branches/[^/]+", route):
        return {
            "name": body.get("name"),
            "commit": {"sha": (body.get("commit") or {}).get("sha")},
            "protected": body.get("protected"),
            "protection": body.get("protection"),
        }
    if re.search(r"/pulls$", route):
        return [
            {
                **_pick(
                    p,
                    "number",
                    "state",
                    "title",
                    "html_url",
                    "created_at",
                    "closed_at",
                    "merged_at",
                    "merge_commit_sha",
                ),
                "head": {"ref": p["head"]["ref"], "sha": p["head"]["sha"]},
                "base": {"ref": p["base"]["ref"]},
            }
            for p in body
        ]
    if re.search(r"/actions/runs$", route):
        return {
            "total_count": body.get("total_count"),
            "workflow_runs": [
                {
                    **_pick(
                        r,
                        "id",
                        "name",
                        "path",
                        "head_branch",
                        "head_sha",
                        "event",
                        "status",
                        "conclusion",
                        "created_at",
                        "run_attempt",
                        "html_url",
                    ),
                    "pull_requests": [
                        {"number": p["number"]} for p in r.get("pull_requests", [])
                    ],
                }
                for r in body.get("workflow_runs", [])
            ],
        }
    if re.search(r"/deployments/\d+/statuses$", route):
        return [_pick(s, "state", "created_at", "environment_url") for s in body]
    if re.search(r"/deployments$", route):
        return [_pick(d, "id", "sha", "ref", "environment", "created_at") for d in body]
    if re.search(r"/rules/branches/", route):
        return [
            {
                "type": r.get("type"),
                **(
                    {"parameters": r["parameters"]}
                    if r.get("type") == "required_status_checks"
                    else {}
                ),
            }
            for r in body
        ]
    if re.search(r"/contents/", route):
        if isinstance(body, list):
            return [_pick(e, "name", "path", "type") for e in body]
        return _pick(body, "name", "path", "type", "content", "encoding")
    if re.match(r"repos/[^/]+/[^/]+$", route):
        return {
            **_pick(body, "full_name", "default_branch", "html_url"),
            "source": _pick(body.get("source"), "full_name"),
        }
    return body
