from datetime import datetime
from pathlib import Path

import pytest
from conftest import (
    FIXTURE_CLOSE,
    FIXTURE_READING_DAY,
    FIXTURE_TIME_ZONE,
    MakeClient,
    sign_in,
)
from course_folders import (
    A_SCALE,
    CALENDAR,
    ONE_STEP,
    TWO_GROUPS,
    front_matter,
    on,
    problems,
    verify,
    with_every_competency,
    write_course_folder,
)
from courses_under_test import (
    DEMO_COURSE,
    FIXTURES,
    TWO_GROUP_FIXTURE,
    CourseFolder,
    OnTheRoster,
)
from fastapi.testclient import TestClient

from app.settings import ConfigurationError, Settings

COURSES = FIXTURES / "courses"


@pytest.fixture
def course() -> CourseFolder:
    return TWO_GROUP_FIXTURE


def test_the_api_serves_the_courses_name_and_each_competencys_title_and_minutes(
    client: TestClient,
) -> None:
    response = client.get("/api/course")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Fixture course"
    assert body["competencies"] == [
        {
            "id": "C1",
            "title": "A fixture Competency with several Steps",
            "minutes": 40,
        },
        {"id": "C2", "title": "A fixture Competency with one Step", "minutes": 25},
        {
            "id": "C3",
            "title": "Another fixture Competency with one Step",
            "minutes": 15,
        },
    ]


def test_a_competencys_page_takes_its_title_from_the_settings(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    folder = write_course_folder(
        tmp_path,
        with_every_competency(),
        {"C1": ("First", 10), "C2": ("Second", 20), "C3": ("Third", 30)},
    )
    client = make_client(settings=on(test_settings, folder))
    sign_in(client, TWO_GROUP_FIXTURE.student.github_id)

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
    result = verify(DEMO_COURSE.folder)

    assert result.returncode == 0, result.stdout + result.stderr


def test_verify_reports_every_settings_problem_and_fails() -> None:
    result = verify(COURSES / "two-settings-problems")

    assert result.returncode != 0
    assert "'name'" in result.stdout
    assert "'title'" in result.stdout


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
    (folder / "course.toml").write_text(
        'name = "Fixture course"\nread_when_none_declared = "roster"\n'
        + TWO_GROUPS
        + A_SCALE
        + CALENDAR,
        encoding="utf-8",
    )

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


SEA_GROUPS = (
    '\n[[groups]]\nname = "Harbour"\nblock = "harbour"\n'
    '\n[[groups]]\nname = "Lighthouse"\nblock = "lighthouse"\n'
)


def course_folder(folder: Path, groups: str, step: str) -> Path:
    return write_course_folder(
        folder,
        with_every_competency(C1=f"## S {{#s minutes=5}}\n\n{step}"),
        groups=groups,
    )


def test_verify_reports_a_group_block_for_a_group_the_settings_do_not_hold(
    tmp_path: Path,
) -> None:
    folder = course_folder(tmp_path, SEA_GROUPS, "::: quay\nx\n:::\n")

    result = verify(folder)

    assert result.returncode != 0
    assert "'::: quay'" in result.stdout


def test_verify_reports_a_step_with_one_groups_block_and_not_anothers(
    tmp_path: Path,
) -> None:
    folder = course_folder(tmp_path, SEA_GROUPS, "::: harbour\nx\n:::\n")

    result = verify(folder)

    assert result.returncode != 0
    assert "step 's'" in result.stdout
    assert "Lighthouse" in result.stdout


def test_verify_passes_a_step_with_every_groups_block(tmp_path: Path) -> None:
    folder = course_folder(
        tmp_path, SEA_GROUPS, "::: harbour\nx\n:::\n\n::: lighthouse\ny\n:::\n"
    )

    result = verify(folder)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param(
            SEA_GROUPS.replace('"Lighthouse"', '"Harbour"'), id="two Groups, one name"
        ),
        pytest.param(
            SEA_GROUPS.replace('"lighthouse"', '"harbour"'), id="two Groups, one block"
        ),
    ],
)
def test_verify_reports_two_groups_sharing_an_id(tmp_path: Path, settings: str) -> None:
    folder = course_folder(tmp_path, settings, "x\n")

    result = verify(folder)

    assert result.returncode != 0
    assert "'harbour'" in result.stdout.lower()


def test_the_app_refuses_to_start_on_a_group_block_the_settings_do_not_hold(
    make_client: MakeClient, test_settings: Settings, tmp_path: Path
) -> None:
    folder = course_folder(tmp_path, SEA_GROUPS, "::: quay\nx\n:::\n")

    with pytest.raises(ConfigurationError, match="quay"):
        make_client(settings=on(test_settings, folder))


def test_verify_reports_a_reading_day_before_the_close() -> None:
    result = verify(COURSES / "reading-day-before-the-close")

    assert result.returncode != 0
    assert "the Reading Day comes before the Close" in result.stdout


def test_the_app_refuses_to_start_on_a_reading_day_before_the_close(
    make_client: MakeClient, test_settings: Settings
) -> None:
    with pytest.raises(ConfigurationError, match="Reading Day comes before the Close"):
        make_client(
            settings=on(test_settings, COURSES / "reading-day-before-the-close")
        )


def test_the_close_and_the_reading_day_are_the_courses_in_its_time_zone(
    signed_in: TestClient,
) -> None:
    page = signed_in.get("/api/competencies/C1").json()

    assert datetime.fromisoformat(page["closes_at"]) == FIXTURE_CLOSE
    assert datetime.fromisoformat(page["reading_day_at"]) == FIXTURE_READING_DAY


def test_a_close_written_with_an_offset_keeps_it(
    make_client: MakeClient,
    test_settings: Settings,
    student: OnTheRoster,
    tmp_path: Path,
) -> None:
    folder = write_course_folder(tmp_path, with_every_competency())
    settings = folder / "course.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace(
            "close = 2030-06-14T23:59:00", "close = 2030-06-14T23:59:00-04:00"
        ),
        encoding="utf-8",
    )
    client = make_client(settings=on(test_settings, folder))
    sign_in(client, student.github_id)

    page = client.get("/api/competencies/C1").json()

    assert datetime.fromisoformat(page["closes_at"]) == datetime(
        2030, 6, 15, 5, 59, tzinfo=FIXTURE_TIME_ZONE
    )
