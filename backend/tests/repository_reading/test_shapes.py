import gzip
from dataclasses import replace
from typing import Any

from app.repository_reading import PointId, RepositoryReading

from .conftest import FIXTURES, MATHUTRICE, Recorded


def c1_refs(reading: RepositoryReading) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in reading["C1"].facts:
        key = f.detail.get("branch") or f"#{f.detail['pull_request']}"
        out[key] = f.detail
    return out


def test_an_empty_repository_says_where_it_looked_never_zero(
    recorded: type[Recorded],
) -> None:
    r = recorded("empty-repository")
    reading = r.reader.read(r.student)

    assert reading.empty
    assert (reading.branches_read, reading.pull_requests_read) == (1, 0)
    assert reading["C1"].facts == []
    assert reading["C1"].nothing_found == ["C1"]
    assert reading.facts_computed_at is not None


def test_work_only_off_the_default_branch_is_found_on_its_branches(
    recorded: type[Recorded],
) -> None:
    r = recorded("work-off-default")
    reading = r.reader.read(r.student)

    refs = c1_refs(reading)
    assert reading.default_branch == "course-2026-fallback-ci"
    assert "course-2026-fallback-ci" not in refs
    assert {"course-2026", "ci/architecture-violation"} <= refs.keys()
    assert not reading.empty


def test_a_pull_request_whose_branch_was_deleted_is_read_from_its_head(
    recorded: type[Recorded],
) -> None:
    r = recorded("deleted-pr-branch")
    reading = r.reader.read(r.student)

    refs = c1_refs(reading)
    assert refs["#1"]["branch_deleted"] is True
    assert {f["path"] for f in refs["#1"]["files"]}
    assert reading.pull_requests_read == 4


def test_commits_under_a_placeholder_email_count_as_the_students_work(
    recorded: type[Recorded],
) -> None:
    raw = gzip.decompress(
        (FIXTURES / "placeholder-email.json.gz").read_bytes()
    ).decode()
    assert "ton.email@exemple.com" in raw

    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)

    lab3 = c1_refs(reading)["codex/deploy-pipeline"]
    assert lab3["lines_added"] > 1000
    assert all(f.credited_to == "student" for f in reading["C1"].facts)


def test_commits_authored_by_claude_count_as_the_students_work(
    recorded: type[Recorded],
) -> None:
    raw = gzip.decompress((FIXTURES / "claude-author.json.gz").read_bytes()).decode()
    assert "claude" in raw.lower()

    r = recorded("claude-author")
    reading = r.reader.read(r.student)

    claude_branches = [b for b in c1_refs(reading) if b.startswith("claude/")]
    assert claude_branches


def test_a_fallback_branch_as_default_is_credited_to_it_not_to_the_student(
    recorded: type[Recorded],
) -> None:
    r = recorded("fallback-default")
    reading = r.reader.read(r.student)

    assert reading.default_branch == "course-2026-fallback-clean-bench"
    assert reading.empty
    contained = [
        f for f in reading["C2"].facts_for(PointId.C2_B) if "Clean Bench" in f.text
    ]
    assert contained and contained[0].credited_to == "course-2026-fallback-clean-bench"
    assert all(
        f.credited_to != "student" for f in reading["C2"].facts_for(PointId.C2_B)
    )


def test_a_ruleset_requiring_architecture_and_test(recorded: type[Recorded]) -> None:
    r = recorded("deleted-pr-branch")
    reading = r.reader.read(r.student)

    (rules,) = reading["C2"].facts_for(PointId.C2_C)
    assert rules.detail["required_checks"] == ["architecture", "test"]
    assert "`architecture` and `test`" in rules.text


def test_deployments_to_both_environments(recorded: type[Recorded]) -> None:
    r = recorded("both-environments")
    reading = r.reader.read(r.student)

    envs = {
        f.detail["environment"]: f.detail for f in reading["C2"].facts_for(PointId.C2_E)
    }
    assert set(envs) == {"staging", "production"}
    assert all(len(d["sha"]) == 40 for d in envs.values())


def test_a_repository_without_deployments_has_nothing_found_for_c2e(
    recorded: type[Recorded],
) -> None:
    r = recorded("deleted-pr-branch")
    reading = r.reader.read(r.student)

    assert "C2.e" in reading["C2"].nothing_found


def test_points_no_repository_can_show_are_named(recorded: type[Recorded]) -> None:
    r = recorded("empty-repository")
    reading = r.reader.read(r.student)

    assert reading["C2"].not_visible == ["C2.f", "C2.g"]
    assert reading["C3"].not_visible == ["C3.a", "C3.c", "C3.d", "C3.f"]


def test_a_red_then_green_pull_request(recorded: type[Recorded]) -> None:
    r = recorded("deleted-pr-branch")
    reading = r.reader.read(r.student)

    assert [
        f.detail["pull_request"] for f in reading["C2"].facts_for(PointId.C2_A)
    ] == [2]


def test_errors_sent_to_posthog_with_an_identity_by_the_students_code(
    recorded: type[Recorded],
) -> None:
    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)

    (fact,) = reading["C3"].facts_for(PointId.C3_B)
    assert fact.credited_to == "student"


def test_a_reading_survives_its_json_round_trip(recorded: type[Recorded]) -> None:
    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)

    assert RepositoryReading.from_dict(reading.to_dict()) == reading


def test_a_reading_stored_before_its_times_were_renamed_still_reads(
    recorded: type[Recorded],
) -> None:
    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)
    stored = reading.to_dict()
    stored["read_at"] = stored.pop("facts_computed_at")
    stored["checked_at"] = stored.pop("last_checked_at")

    assert RepositoryReading.from_dict(stored) == reading


def test_ref_analyses_stored_before_they_had_a_type_are_read_again(
    recorded: type[Recorded],
) -> None:
    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)
    stored = reading.to_dict()
    stored["refs"]["analyses"] = {
        sha: {"files": [], "closest": None} for sha in stored["refs"]["analyses"]
    }

    again = r.reader.read_now(r.student, previous=RepositoryReading.from_dict(stored))

    assert again.competencies == reading.competencies


def test_a_readings_student_is_stored_under_the_keys_it_always_had(
    recorded: type[Recorded],
) -> None:
    r = recorded("placeholder-email")
    reading = r.reader.read(r.student)

    assert reading.to_dict()["student"] == {
        "login": r.student.login,
        "project": r.student.group,
        "evidence_project": r.student.evidence_project,
    }


def test_a_group_without_an_upstream_repository_is_read_on_its_own_history(
    recorded: type[Recorded],
) -> None:
    r = recorded("empty-repository")
    student = replace(r.student, upstream=None)
    sha = "d39af33d97a4d6f5076e9ef2a8755ebb76ce2ff8"
    repo = f"repos/{student.evidence_project}/git"
    r.github.set(
        f"{repo}/trees/{sha}?recursive=1",
        200,
        {"tree": [{"path": "README.md", "type": "blob"}]},
    )
    r.github.set(
        f"{repo}/commits/{sha}", 200, {"committer": {"date": "2026-11-01T10:00:00Z"}}
    )

    reading = r.reader.read(student)

    (fact,) = reading["C1"].facts
    assert fact.credited_to == "student"
    assert fact.detail["files"] == [{"path": "README.md"}]
    assert fact.detail["closest"] is None
    assert not any(MATHUTRICE in request for request in r.github.requests)
