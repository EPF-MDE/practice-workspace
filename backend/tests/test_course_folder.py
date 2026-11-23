import subprocess
import sys
from pathlib import Path

import pytest
from conftest import FIXTURES, MakeClient
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


def test_the_api_serves_the_courses_name(client: TestClient) -> None:
    response = client.get("/api/course")

    assert response.status_code == 200
    assert response.json() == {"name": "Fixture course"}


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


def test_verify_reports_a_content_problem_beside_a_settings_problem(
    tmp_path: Path,
) -> None:
    (tmp_path / "c1.md").write_text(
        "---\ncompetency: C1\ntitle: T\n---\n\n## S {#s minutes=5}\n\n"
        "::: answr\nx\n:::\n"
    )

    result = verify(tmp_path)

    assert result.returncode != 0
    assert "course.toml" in result.stdout
    assert "c1.md" in result.stdout
