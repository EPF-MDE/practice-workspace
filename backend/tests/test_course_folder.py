import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ADA_OF_OCEENS, FIXTURES, MakeClient, sign_in
from course_folders import (
    ONE_STEP,
    front_matter,
    with_every_competency,
    write_course_folder,
)
from fastapi.testclient import TestClient

from app.main import ConfigurationError
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]
DEMO_COURSE = BACKEND.parent / "demo-course"
COURSES = FIXTURES / "courses"


def verify(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app", "verify", str(folder)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


def on(test_settings: Settings, folder: Path) -> Settings:
    return test_settings.model_copy(update={"course_folder": str(folder)})


def test_the_api_serves_the_courses_name_and_each_competencys_title_and_minutes(
    client: TestClient,
) -> None:
    response = client.get("/api/course")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Fixture course",
        "competencies": [
            {
                "id": "C1",
                "title": "Design a resilient web architecture under "
                "non-functional constraints",
                "minutes": 40,
            },
            {"id": "C2", "title": "A fixture Competency with one Step", "minutes": 25},
            {
                "id": "C3",
                "title": "Another fixture Competency with one Step",
                "minutes": 15,
            },
        ],
    }


def test_a_competencys_page_takes_its_title_from_the_settings(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    folder = write_course_folder(
        tmp_path,
        with_every_competency(),
        {"C1": ("First", 10), "C2": ("Second", 20), "C3": ("Third", 30)},
    )
    client = make_client(settings=on(test_settings, folder))
    sign_in(client, ADA_OF_OCEENS)

    assert client.get("/api/competencies/C2").json()["title"] == "Second"


def test_the_app_refuses_to_start_on_a_course_folder_with_no_settings_file(
    make_client: MakeClient, test_settings: Settings
) -> None:
    with pytest.raises(ConfigurationError, match=r"course\.toml"):
        make_client(settings=on(test_settings, COURSES / "no-settings"))


def test_the_app_refuses_to_start_on_invalid_settings_and_names_each_problem(
    make_client: MakeClient, test_settings: Settings
) -> None:
    with pytest.raises(ConfigurationError) as refusal:
        make_client(settings=on(test_settings, COURSES / "two-settings-problems"))

    assert "'name'" in str(refusal.value)
    assert "'title'" in str(refusal.value)


def test_verify_passes_the_demo_course() -> None:
    result = verify(DEMO_COURSE)

    assert result.returncode == 0, result.stdout + result.stderr


def test_verify_reports_every_settings_problem_and_fails() -> None:
    result = verify(COURSES / "two-settings-problems")

    assert result.returncode != 0
    assert "'name'" in result.stdout
    assert "'title'" in result.stdout


def problems(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("✖")]


def test_the_app_refuses_to_start_on_a_course_folder_missing_the_content_of_c2(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    content = with_every_competency()
    del content["C2"]
    folder = write_course_folder(tmp_path, content)

    with pytest.raises(ConfigurationError, match=r"c2\.md"):
        make_client(settings=on(test_settings, folder))


def test_verify_names_each_competency_whose_content_is_missing(
    tmp_path: Path,
) -> None:
    folder = write_course_folder(tmp_path, {"C1": ONE_STEP})

    result = verify(folder)

    assert result.returncode != 0
    assert [p for p in problems(result) if "C2" in p or "c2.md" in p] != []
    assert [p for p in problems(result) if "C3" in p or "c3.md" in p] != []
    assert [p for p in problems(result) if "C1" in p or "c1.md" in p] == []


def test_verify_refuses_content_for_a_competency_beyond_c3(tmp_path: Path) -> None:
    folder = write_course_folder(tmp_path, with_every_competency(C4=ONE_STEP))

    result = verify(folder)

    assert result.returncode != 0
    assert len(problems(result)) == 1
    assert "C4" in problems(result)[0]


def test_verify_refuses_a_c4_file_holding_the_content_of_c1(tmp_path: Path) -> None:
    folder = write_course_folder(tmp_path, with_every_competency())
    (folder / "c4.md").write_text(front_matter("C1") + ONE_STEP)

    result = verify(folder)

    assert result.returncode != 0
    assert len(problems(result)) == 1
    assert "c4.md" in problems(result)[0]


def test_verify_names_a_competency_the_settings_miss_and_one_they_hold_beyond_c3(
    tmp_path: Path,
) -> None:
    folder = write_course_folder(
        tmp_path,
        with_every_competency(),
        {"C1": ("First", 10), "C3": ("Third", 30), "C4": ("Fourth", 40)},
    )

    result = verify(folder)

    assert result.returncode != 0
    assert len(problems(result)) == 2
    assert any("C2" in p and "course.toml" in p for p in problems(result))
    assert any("C4" in p and "course.toml" in p for p in problems(result))


def test_verify_names_each_competency_when_the_settings_hold_none(
    tmp_path: Path,
) -> None:
    folder = write_course_folder(tmp_path, with_every_competency())
    (folder / "course.toml").write_text('name = "Fixture course"\n')

    result = verify(folder)

    assert result.returncode != 0
    assert len(problems(result)) == 3
    for competency in ("C1", "C2", "C3"):
        assert any(competency in p and "course.toml" in p for p in problems(result))


def test_verify_refuses_a_title_in_a_competencys_front_matter(tmp_path: Path) -> None:
    folder = write_course_folder(tmp_path, with_every_competency())
    (folder / "c1.md").write_text("---\ncompetency: C1\ntitle: T\n---\n\n" + ONE_STEP)

    result = verify(folder)

    assert result.returncode != 0
    assert len(problems(result)) == 1
    assert "c1.md" in problems(result)[0]


def test_verify_reports_a_content_problem_beside_a_settings_problem(
    tmp_path: Path,
) -> None:
    (tmp_path / "c1.md").write_text(
        "---\ncompetency: C1\n---\n\n## S {#s minutes=5}\n\n::: answr\nx\n:::\n"
    )

    result = verify(tmp_path)

    assert result.returncode != 0
    assert "course.toml" in result.stdout
    assert "c1.md" in result.stdout
