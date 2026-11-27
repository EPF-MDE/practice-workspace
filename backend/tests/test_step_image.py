import re

import pytest
from courses_under_test import TWO_GROUP_FIXTURE, on_the_two_group_fixture
from fastapi.testclient import TestClient

PAGE = "/api/competencies/C1"
HARBOUR = TWO_GROUP_FIXTURE.folder / "images" / "harbour.png"

pytestmark = on_the_two_group_fixture


def image_sources(signed_in: TestClient) -> list[str]:
    page = signed_in.get(PAGE).json()
    step = next(s for s in page["steps"] if s["id"] == "read-the-chain")
    html = "".join(b.get("html", "") for b in step["blocks"])
    return re.findall(r'<img src="([^"]+)" alt="The harbour the chain starts', html)


def test_a_steps_image_is_served_from_the_course_folder_however_its_path_is_encoded(
    signed_in: TestClient,
) -> None:
    sources = image_sources(signed_in)

    assert len(sources) == 2
    for src in sources:
        response = signed_in.get(src)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == HARBOUR.read_bytes()


@pytest.mark.parametrize(
    "path",
    [
        "/api/course/images/%2E%2E/course.toml",
        "/api/course/images/..%2Fc1.md",
        "/api/course/images/%2E%2E%2Froster.csv",
        "/api/course/images/%2Fetc%2Fpasswd",
        "/api/course/images//etc/passwd",
        f"/api/course/images/{HARBOUR.as_posix()}",
        "/api/course/images/notes.txt",
        "/api/course/images/c1.md",
        "/api/course/images/harbour.jpg",
    ],
)
def test_no_path_reads_another_file_than_an_image_of_the_course_folder(
    signed_in: TestClient, path: str
) -> None:
    response = signed_in.get(path)

    assert response.status_code == 404
    assert response.content != HARBOUR.read_bytes()


def test_an_image_only_the_instructor_material_shows_is_not_served(
    signed_in: TestClient,
) -> None:
    assert signed_in.get("/api/course/images/instructor-only.png").status_code == 404


def test_a_steps_image_is_not_served_before_sign_in(client: TestClient) -> None:
    assert client.get("/api/course/images/harbour.png").status_code == 401
