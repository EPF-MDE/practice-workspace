from pathlib import Path

import pytest
from conftest import MakeClient
from course_folders import problems, verify
from courses_under_test import FIXTURES

from app.settings import ConfigurationError, Settings

VERIFY = FIXTURES / "courses" / "verify"


def test_verify_passes_a_valid_course_folder() -> None:
    result = verify(VERIFY / "valid")

    assert result.returncode == 0, result.stdout + result.stderr
    assert problems(result) == []


@pytest.mark.parametrize(
    ("folder", "where", "problem"),
    [
        ("unknown-directive", "c1.md, step 'sail'", "'::: anwser'"),
        ("unclosed-block", "c1.md, step 'sail'", "'::: answer' is never closed"),
        ("two-steps-one-id", "c1.md, step 'sail'", "steps share this id"),
        ("two-points-one-id", "c1.md, step 'closing'", "point C1.a shares its id"),
        ("answer-without-field", "c1.md, step 'sail'", "no field to answer in"),
        ("missing-group-block", "c1.md, step 'sail'", "none for Lighthouse"),
        ("unknown-group-block", "c1.md, step 'sail'", "'::: quay'"),
        ("instructor-material", "c1.md, step 'sail'", "'banding anchor'"),
        ("not-validated", "c1.md, step 'sail'", "'TO VALIDATE' would be served"),
        ("unknown-level", "c1.md, step 'closing'", "level=someday"),
        ("missing-drawing", "c1.md, step 'redraw'", "'drawings/harbour.json'"),
    ],
)
def test_verify_names_the_problem_its_file_and_its_step_and_fails(
    folder: str, where: str, problem: str
) -> None:
    result = verify(VERIFY / folder)

    assert result.returncode != 0
    assert len(problems(result)) == 1, result.stdout
    assert where in problems(result)[0]
    assert problem in problems(result)[0]


SEVERAL_PROBLEMS = [
    ("c1.md, step 'sail'", "'::: anwser'"),
    ("c2.md, step 'light'", "'TO VALIDATE' would be served"),
    ("c3.md, step 'ebb'", "steps share this id"),
]


def test_verify_reports_problems_in_different_files_at_once() -> None:
    result = verify(VERIFY / "several-problems")

    assert result.returncode != 0
    assert len(problems(result)) == len(SEVERAL_PROBLEMS), result.stdout
    for where, problem in SEVERAL_PROBLEMS:
        assert any(where in p and problem in p for p in problems(result))


def with_c1(folder: Path, steps: str) -> Path:
    for name in ("course.toml", "c1.md", "c2.md", "c3.md"):
        (folder / name).write_text((VERIFY / "valid" / name).read_text())
    (folder / "c1.md").write_text(f"---\ncompetency: C1\n---\n\n{steps}")
    return folder


def test_verify_reports_every_problem_in_one_file(tmp_path: Path) -> None:
    with_c1(
        tmp_path,
        "## Sail {#sail minutes=5}\n\n::: anwser\nx\n:::\n\n"
        "## Moor {#moor minutes=5}\n\nRead the banding anchor.\n\n"
        "## Dock {#dock minutes=5}\n\n::: answer\nx\n:::\n",
    )

    result = verify(tmp_path)

    assert result.returncode != 0
    steps = ("step 'sail'", "step 'moor'", "step 'dock'")
    assert len(problems(result)) == len(steps), result.stdout
    for step in steps:
        assert any(step in p for p in problems(result))


def test_a_step_waiting_for_a_broken_one_is_not_reported_too(tmp_path: Path) -> None:
    result = verify(
        with_c1(
            tmp_path,
            "## Sail {#sail}\n\n::: field {#route}\n:::\n\n"
            "## Moor {#moor minutes=5 after=sail}\n\nMoor.\n",
        )
    )

    assert result.returncode != 0
    assert len(problems(result)) == 1, result.stdout
    assert "step 'sail'" in problems(result)[0]


def test_a_marker_in_a_step_with_another_problem_is_reported_too(
    tmp_path: Path,
) -> None:
    result = verify(
        with_c1(
            tmp_path, "## Sail {#sail minutes=5}\n\nTO VALIDATE\n\n::: anwser\nx\n:::\n"
        )
    )

    assert result.returncode != 0
    assert len(problems(result)) == 2, result.stdout
    assert any("'::: anwser'" in p for p in problems(result))
    assert any("'TO VALIDATE' would be served" in p for p in problems(result))


def test_a_to_get_there_with_no_level_is_named_when_the_settings_are_broken(
    tmp_path: Path,
) -> None:
    closing = (VERIFY / "unknown-level" / "c1.md").read_text().split("---\n")[-1]
    with_c1(tmp_path, closing.replace(" {level=someday}", ""))
    (tmp_path / "course.toml").write_text("name = \n")

    result = verify(tmp_path)

    assert result.returncode != 0
    assert any(
        "step 'closing'" in p and "needs a level" in p for p in problems(result)
    ), result.stdout


def test_a_drawing_that_is_no_json_is_named(tmp_path: Path) -> None:
    redraw = (VERIFY / "missing-drawing" / "c1.md").read_text().split("---\n")[-1]
    (tmp_path / "drawings").mkdir()
    (tmp_path / "drawings" / "harbour.json").write_text("not json")

    result = verify(with_c1(tmp_path, redraw))

    assert result.returncode != 0
    assert len(problems(result)) == 1, result.stdout
    assert "'drawings/harbour.json'" in problems(result)[0]


def test_a_problem_repeated_in_two_steps_sharing_an_id_is_reported_once(
    tmp_path: Path,
) -> None:
    sail = "## Sail {#sail minutes=5}\n\nTO VALIDATE\n\n"

    result = verify(with_c1(tmp_path, sail + sail))

    assert result.returncode != 0
    assert len(problems(result)) == 2, result.stdout


def test_the_app_refuses_to_start_on_a_broken_course_folder_naming_each_problem(
    make_client: MakeClient, test_settings: Settings
) -> None:
    settings = test_settings.model_copy(
        update={"course_folder": str(VERIFY / "several-problems")}
    )

    with pytest.raises(ConfigurationError) as refusal:
        make_client(settings=settings)

    for where, problem in SEVERAL_PROBLEMS:
        assert where in str(refusal.value)
        assert problem in str(refusal.value)
