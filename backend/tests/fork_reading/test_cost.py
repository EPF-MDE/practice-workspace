"""The reading's cost in GitHub requests (#460, "The cost"), and its caching by pair
of SHAs."""

import copy
import re

from app.fork_reading import ForkReader, InMemoryReadings, Response, StudentFork

from .conftest import NOW, Recorded


def test_reading_a_fork_again_compares_nothing_already_compared(
    recorded: type[Recorded],
) -> None:
    r = recorded("deleted-pr-branch")
    r.reader.read(r.student)
    first = len(r.compares())
    assert first > 0

    # Forget the stored reading, keep the reader and its cache.
    r.readings.readings.clear()
    r.reader.read(r.student)

    assert len(r.compares()) == first


def test_a_refresh_with_no_changed_ref_costs_at_most_2_requests(
    recorded: type[Recorded],
) -> None:
    r = recorded("placeholder-email")
    before = r.reader.read(r.student)
    r.github.requests.clear()

    after = r.reader.refresh(r.student)

    assert len(r.github.requests) <= 2
    assert after.competencies == before.competencies
    assert (
        r.readings.writes == 1
    )  # the first reading only: a check with no change writes nothing


def test_a_refresh_recomputes_only_the_ref_that_moved(recorded: type[Recorded]) -> None:
    r = recorded("deleted-pr-branch")
    reader_cold = ForkReader(
        r.github, r.readings, now=lambda: NOW
    )  # no comparison in memory
    r.reader.read(r.student)

    # A push to `course-2026`: its tip becomes a new commit, compared as the old tip
    # was.
    branches_path = f"repos/{r.student.fork}/branches?per_page=100"
    branches = copy.deepcopy(r.github.recording[branches_path]["body"])
    moved = next(b for b in branches if b["name"] == "course-2026")
    old, new = moved["commit"]["sha"], "f" * 40
    moved["commit"]["sha"] = new
    r.github.set(branches_path, 200, branches)
    for path, resp in list(r.github.recording.items()):
        if "/compare/" in path and path.split("?")[0].endswith(f"...{old}"):
            r.github.set(
                path.replace(f"...{old}", f"...{new}"),
                resp["status"],
                resp["body"],
                resp.get("next_page"),
            )
    r.github.requests.clear()

    reading = reader_cold.refresh(r.student)

    compared_heads = {
        p.split("?")[0].rsplit("...", 1)[1]
        for p in r.github.requests
        if "/compare/" in p
    }
    assert compared_heads == {new}
    assert reading.refs["branches"]["course-2026"] == new


class LargestShape:
    """A fork shaped like the largest measured (19 branches, 16 pull requests), on
    OcéENS's 13 upstream branches."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.fork = "student/OceENS"
        self.branches = [
            {"name": f"b{i}", "commit": {"sha": f"{i:040x}"}, "protected": False}
            for i in range(19)
        ]
        # Half of the pull requests point at a branch's tip; the other half at heads of
        # deleted branches.
        self.pulls = [
            {
                "number": n,
                "state": "closed",
                "title": f"pr {n}",
                "html_url": "",
                "created_at": "2026-10-01T00:00:00Z",
                "closed_at": "2026-10-02T00:00:00Z",
                "merged_at": None,
                "merge_commit_sha": None,
                "head": {"ref": f"gone{n}", "sha": f"{(n if n % 2 else 100 + n):040x}"},
                "base": {"ref": "b0"},
            }
            for n in range(16)
        ]
        names = ["course-2026"] + [f"course-2026-x{i}" for i in range(12)]
        self.upstream = [
            {"name": n, "commit": {"sha": f"{1000 + i:040x}"}}
            for i, n in enumerate(names)
        ]

    def get(self, path: str) -> Response:
        self.requests.append(path)
        route = path.split("?")[0]
        if route == f"repos/{self.fork}":
            return Response(200, {"default_branch": "b0"})
        if route == f"repos/{self.fork}/branches":
            return Response(200, self.branches)
        if route == f"repos/{self.fork}/pulls":
            return Response(200, self.pulls)
        if route == "repos/EPF-MDE/OceENS/branches":
            return Response(200, self.upstream)
        if "/compare/" in route:
            return Response(
                200,
                {
                    "status": "diverged",
                    "ahead_by": 3,
                    "behind_by": 2,
                    "html_url": "",
                    "merge_base_commit": {"sha": "0" * 40},
                    "commits": [
                        {
                            "sha": "c",
                            "commit": {
                                "author": {"date": "2026-10-13T00:00:00Z"},
                                "committer": {"date": "2026-10-13T00:00:00Z"},
                            },
                        }
                    ],
                    "files": [
                        {
                            "filename": "app/feature.py",
                            "status": "added",
                            "additions": 40,
                            "deletions": 0,
                            "changes": 40,
                        }
                    ],
                },
            )
        if re.search(r"/actions/runs$", route):
            return Response(200, {"total_count": 0, "workflow_runs": []})
        return Response(200, [])


def test_a_full_reading_of_the_largest_shape_stays_within_its_estimate() -> None:
    github = LargestShape()
    reader = ForkReader(github, InMemoryReadings(), now=lambda: NOW)

    reading = reader.read(StudentFork("student", "OcéENS", github.fork))

    assert (reading.branches_read, reading.pull_requests_read) == (19, 16)
    assert len(github.requests) <= 500
