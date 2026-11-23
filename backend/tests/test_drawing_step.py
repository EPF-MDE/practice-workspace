import base64
import json
from datetime import datetime
from typing import Any

import pytest
from conftest import ADA_OF_OCEENS, GRACE_OF_MATHUTRICE, MakeClient, sign_in
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


@pytest.fixture
def ada(client: TestClient) -> TestClient:
    sign_in(client, ADA_OF_OCEENS)
    return client


def test_before_the_drawing_the_example_and_the_prompt_show_and_the_reference_is_withheld(  # noqa: E501
    ada: TestClient,
) -> None:
    response = ada.get(PAGE)
    page = response.json()

    assert step(page)["kind"] == "drawing"
    example = block(page, "example-drawing")
    assert "EXAMPLE-SNAPSHOT" in json.dumps(example["snapshot"]["document"])
    assert "EXAMPLE-CAPTION" in example["caption_html"]
    assert "OCEENS-PROMPT" in block(page, "canvas")["prompt_html"]
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
    ada: TestClient,
) -> None:
    sent = ada.post(DRAWING, json=SEND)

    assert sent.status_code == 200
    body = sent.json()
    assert body["version"] == 1
    assert body["png_bytes"] == len(PNG)
    reference = body["reference"]
    assert reference["locked"] is False
    assert "OCEENS-REFERENCE-SNAPSHOT" in json.dumps(reference["snapshot"]["document"])
    assert "OCEENS-REFERENCE-CAPTION" in reference["caption_html"]
    assert [(c["id"], c["point"]) for c in reference["check_points"]] == [
        ("oceens-1", "C1.b"),
        ("oceens-2", "C1.b"),
        ("oceens-3", "C1.b"),
    ]
    assert "OCEENS-CHECK-2" in reference["check_points"][1]["html"]


def test_once_sent_the_page_shows_the_reference_and_the_drawing_sent(
    ada: TestClient,
) -> None:
    ada.post(DRAWING, json=SEND)

    page = ada.get(PAGE).json()

    assert block(page, "reference-drawing")["locked"] is False
    assert step(page)["drawing"]["version"] == 1
    assert block(page, "reference-drawing", "redraw-more")["locked"] is True, (
        "another drawing step stays locked"
    )


def test_a_student_receives_their_groups_reference(client: TestClient) -> None:
    sign_in(client, GRACE_OF_MATHUTRICE)

    reference = client.post(DRAWING, json=SEND).json()["reference"]

    assert "MATHUTRICE-REFERENCE-CAPTION" in reference["caption_html"]
    assert len(reference["check_points"]) == 4


def test_a_new_version_replaces_the_drawing_and_is_read_back(ada: TestClient) -> None:
    ada.post(DRAWING, json=SEND)
    second = {
        "document": {"store": {"shape:v2": {"id": "shape:v2"}}, "schema": {}},
        "session": {},
    }

    sent = ada.post(DRAWING, json={**SEND, "snapshot": second}).json()

    assert sent["version"] == 2
    mine = ada.get(DRAWING).json()
    assert mine["snapshot"] == second and mine["version"] == 2
    assert step(ada.get(PAGE).json())["drawing"]["version"] == 2


def test_a_drawing_never_sent_is_not_found(ada: TestClient) -> None:
    assert ada.get(DRAWING).status_code == 404


def test_the_student_ticks_the_check_points_their_drawing_missed(
    ada: TestClient,
) -> None:
    ada.post(DRAWING, json=SEND)

    ticked = ada.post(CHECK_POINTS, json={"missed": ["oceens-1", "oceens-3"]})

    assert ticked.status_code == 200
    assert step(ada.get(PAGE).json())["missed_check_points"] == ["oceens-1", "oceens-3"]
    ada.post(CHECK_POINTS, json={"missed": []})
    assert step(ada.get(PAGE).json())["missed_check_points"] == []


def test_check_points_wait_for_the_drawing(ada: TestClient) -> None:
    assert ada.post(CHECK_POINTS, json={"missed": ["oceens-1"]}).status_code == 409


def test_only_the_references_check_points_can_be_ticked(ada: TestClient) -> None:
    ada.post(DRAWING, json=SEND)

    assert ada.post(CHECK_POINTS, json={"missed": ["math-1"]}).status_code == 422


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
    ada: TestClient, body: dict[str, Any]
) -> None:
    assert ada.post(DRAWING, json=body).status_code == 422


def test_a_drawing_sent_to_a_step_without_canvas_is_refused(ada: TestClient) -> None:
    assert (
        ada.post(f"{PAGE}/steps/guided-calculation/drawing", json=SEND).status_code
        == 422
    )


def test_a_drawing_too_large_is_refused(ada: TestClient) -> None:
    huge = base64.b64encode(PNG + b"\x00" * 6_000_000).decode()

    assert ada.post(DRAWING, json={**SEND, "png_base64": huge}).status_code == 413


def test_after_the_close_no_drawing_and_no_tick_is_sent(
    make_client: MakeClient, test_settings: Settings, past: datetime
) -> None:
    client = make_client(settings=test_settings.model_copy(update={"closes_at": past}))
    sign_in(client, ADA_OF_OCEENS)

    drawing = client.post(DRAWING, json=SEND)

    assert drawing.status_code == 403 and "closed" in drawing.json()["detail"]
    assert client.post(CHECK_POINTS, json={"missed": []}).status_code == 403


def test_the_optional_redraw_says_so_and_nothing_waits_for_it(ada: TestClient) -> None:
    page = ada.get(PAGE).json()

    assert step(page, "redraw-more")["optional"] is True
    assert step(page)["optional"] is False


def test_the_page_carries_the_tldraw_licence_key(
    make_client: MakeClient, test_settings: Settings
) -> None:
    client = make_client(
        settings=test_settings.model_copy(update={"tldraw_license_key": "tldraw-key"})
    )
    sign_in(client, ADA_OF_OCEENS)

    assert client.get(PAGE).json()["tldraw_license_key"] == "tldraw-key"
