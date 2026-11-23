import base64
import json
from typing import Any

import pytest
from conftest import AFTER_THE_CLOSE, MakeClient, sign_in
from courses_under_test import CourseFolder, OnTheRoster, on_the_two_group_fixture
from fastapi.testclient import TestClient

from app.settings import Settings

PAGE = "/api/competencies/C1"
DRAWING = f"{PAGE}/steps/redraw/drawing"
CHECK_POINTS = f"{PAGE}/steps/redraw/check-points"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
SNAPSHOT = {
    "document": {"store": {"shape:mine": {"id": "shape:mine"}}, "schema": {}},
    "session": {},
}
SEND = {"png_base64": base64.b64encode(PNG).decode(), "snapshot": SNAPSHOT}


def step(page: dict[str, Any], step_id: str = "redraw") -> dict[str, Any]:
    return next(s for s in page["steps"] if s["id"] == step_id)


def block(page: dict[str, Any], kind: str, step_id: str = "redraw") -> dict[str, Any]:
    return next(b for b in step(page, step_id)["blocks"] if b["type"] == kind)


def test_before_the_drawing_the_example_and_the_prompt_show_and_the_reference_is_withheld(  # noqa: E501
    signed_in: TestClient, student: OnTheRoster
) -> None:
    response = signed_in.get(PAGE)
    page = response.json()

    assert step(page)["kind"] == "drawing"
    example = block(page, "example-drawing")
    assert "EXAMPLE-SNAPSHOT" in json.dumps(example["snapshot"]["document"])
    assert "EXAMPLE-CAPTION" in example["caption_html"]
    assert student.marked("PROMPT") in block(page, "canvas")["prompt_html"]
    assert block(page, "reference-drawing") == {
        "type": "reference-drawing",
        "locked": True,
        "snapshot": None,
        "caption_html": None,
        "check_points": None,
    }
    for withheld in ("REFERENCE-SNAPSHOT", "REFERENCE-CAPTION", "CHECK-"):
        assert withheld not in response.text
    assert step(page)["drawing"] is None


def test_sending_the_drawing_returns_the_reference_and_its_check_points(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    sent = signed_in.post(DRAWING, json=SEND)

    assert sent.status_code == 200
    body = sent.json()
    assert body["version"] == 1
    assert body["png_bytes"] == len(PNG)
    reference = body["reference"]
    assert reference["locked"] is False
    snapshot = json.dumps(reference["snapshot"]["document"])
    assert student.marked("REFERENCE-SNAPSHOT") in snapshot
    assert student.marked("REFERENCE-CAPTION") in reference["caption_html"]
    assert [(c["id"], c["point"]) for c in reference["check_points"]] == [
        (student.check_point(1), "C1.b"),
        (student.check_point(2), "C1.b"),
        (student.check_point(3), "C1.b"),
    ]
    assert student.marked("CHECK-2") in reference["check_points"][1]["html"]


def test_once_sent_the_page_shows_the_reference_and_the_drawing_sent(
    signed_in: TestClient,
) -> None:
    signed_in.post(DRAWING, json=SEND)

    page = signed_in.get(PAGE).json()

    assert block(page, "reference-drawing")["locked"] is False
    assert step(page)["drawing"]["version"] == 1
    assert block(page, "reference-drawing", "redraw-more")["locked"] is True, (
        "another drawing step stays locked"
    )


def test_a_student_receives_their_groups_reference(
    client: TestClient, course: CourseFolder
) -> None:
    for student in course.one_per_group:
        sign_in(client, student.github_id)

        reference = client.post(DRAWING, json=SEND).json()["reference"]

        assert student.marked("REFERENCE-CAPTION") in reference["caption_html"]
        for other in course.others_marked(student, "REFERENCE-CAPTION"):
            assert other not in reference["caption_html"]
        assert {c["id"].rsplit("-", 1)[0] for c in reference["check_points"]} == {
            student.block
        }


def test_a_new_version_replaces_the_drawing_and_is_read_back(
    signed_in: TestClient,
) -> None:
    signed_in.post(DRAWING, json=SEND)
    second = {
        "document": {"store": {"shape:v2": {"id": "shape:v2"}}, "schema": {}},
        "session": {},
    }

    sent = signed_in.post(DRAWING, json={**SEND, "snapshot": second}).json()

    assert sent["version"] == 2
    mine = signed_in.get(DRAWING).json()
    assert mine["snapshot"] == second and mine["version"] == 2
    assert step(signed_in.get(PAGE).json())["drawing"]["version"] == 2


def test_a_drawing_never_sent_is_not_found(signed_in: TestClient) -> None:
    assert signed_in.get(DRAWING).status_code == 404


def test_the_student_ticks_the_check_points_their_drawing_missed(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    signed_in.post(DRAWING, json=SEND)
    missed = [student.check_point(1), student.check_point(3)]

    ticked = signed_in.post(CHECK_POINTS, json={"missed": missed})

    assert ticked.status_code == 200
    assert step(signed_in.get(PAGE).json())["missed_check_points"] == missed
    signed_in.post(CHECK_POINTS, json={"missed": []})
    assert step(signed_in.get(PAGE).json())["missed_check_points"] == []


def test_check_points_wait_for_the_drawing(
    signed_in: TestClient, student: OnTheRoster
) -> None:
    missed = {"missed": [student.check_point(1)]}

    assert signed_in.post(CHECK_POINTS, json=missed).status_code == 409


@on_the_two_group_fixture
def test_on_two_groups_only_the_references_check_points_can_be_ticked(
    signed_in: TestClient, course: CourseFolder
) -> None:
    signed_in.post(DRAWING, json=SEND)
    another_groups = {"missed": [course.another.check_point(1)]}

    assert signed_in.post(CHECK_POINTS, json=another_groups).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            {**SEND, "png_base64": base64.b64encode(b"GIF89a").decode()},
            id="not a PNG",
        ),
        pytest.param(
            {**SEND, "png_base64": "not base64!"},
            id="not base64",
        ),
        pytest.param(
            {**SEND, "snapshot": {"shapes": []}},
            id="not a tldraw snapshot",
        ),
    ],
)
def test_a_drawing_that_is_not_one_is_refused(
    signed_in: TestClient, body: dict[str, Any]
) -> None:
    assert signed_in.post(DRAWING, json=body).status_code == 422


def test_a_drawing_sent_to_a_step_without_canvas_is_refused(
    signed_in: TestClient,
) -> None:
    assert (
        signed_in.post(
            f"{PAGE}/steps/guided-calculation/drawing", json=SEND
        ).status_code
        == 422
    )


def test_a_drawing_too_large_is_refused(signed_in: TestClient) -> None:
    huge = base64.b64encode(PNG + b"\x00" * 6_000_000).decode()

    assert signed_in.post(DRAWING, json={**SEND, "png_base64": huge}).status_code == 413


def test_after_the_close_no_drawing_and_no_tick_is_sent(
    make_client: MakeClient,
    student: OnTheRoster,
) -> None:
    client = make_client(now=AFTER_THE_CLOSE)
    sign_in(client, student.github_id)

    drawing = client.post(DRAWING, json=SEND)

    assert drawing.status_code == 403 and "closed" in drawing.json()["detail"]
    assert client.post(CHECK_POINTS, json={"missed": []}).status_code == 403


def test_the_optional_redraw_says_so_and_nothing_waits_for_it(
    signed_in: TestClient,
) -> None:
    page = signed_in.get(PAGE).json()

    assert step(page, "redraw-more")["optional"] is True
    assert step(page)["optional"] is False


def test_the_page_carries_the_tldraw_licence_key(
    make_client: MakeClient, test_settings: Settings, student: OnTheRoster
) -> None:
    client = make_client(
        settings=test_settings.model_copy(update={"tldraw_license_key": "tldraw-key"})
    )
    sign_in(client, student.github_id)

    assert client.get(PAGE).json()["tldraw_license_key"] == "tldraw-key"
