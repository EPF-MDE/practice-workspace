import base64
from datetime import datetime
from typing import Any

import pytest
from conftest import ADA, MakeClient, c1_levels, sign_in
from fastapi.testclient import TestClient

from app.settings import Settings

PAGE = "/api/competencies/C1"
SELF = f"{PAGE}/self-assessment"
LINK = "https://github.com/ada/notes/blob/main/README.md#L3"
DRAWING = {
    "png_base64": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode(),
    "snapshot": {"document": {"store": {}, "schema": {}}},
}


def closing(page: dict[str, Any]) -> dict[str, Any]:
    return next(s for s in page["steps"] if s["id"] == "closing")


def points(page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["id"]: b for b in closing(page)["blocks"] if b["type"] == "point"}


@pytest.fixture
def ada(client: TestClient) -> TestClient:
    sign_in(client, ADA)
    return client


def at(
    make_client: MakeClient,
    test_settings: Settings,
    closes_at: datetime,
    reading_day_at: datetime,
) -> TestClient:
    client = make_client(
        settings=test_settings.model_copy(
            update={"closes_at": closes_at, "reading_day_at": reading_day_at}
        )
    )
    sign_in(client, ADA)
    return client


def test_each_point_shows_its_id_band_and_proof_sentence(ada: TestClient) -> None:
    shown = points(ada.get(PAGE).json())

    assert [(p["id"], p["band"]) for p in shown.values()] == [
        ("C1.a", "Basic"),
        ("C1.b", "Solid"),
        ("C1.e", "Outstanding"),
    ]
    assert "WHERE-PROOF" in shown["C1.b"]["proof_html"]


def test_the_page_has_no_self_assessment_before_the_first_send(ada: TestClient) -> None:
    assert ada.get(PAGE).json()["self_assessment"] is None


def test_levels_sent_are_read_back_dated_with_their_version(ada: TestClient) -> None:
    sent = ada.post(SELF, json=c1_levels(a="understand", b="redo", e="not-yet"))

    assert sent.status_code == 200
    mine = ada.get(PAGE).json()["self_assessment"]
    assert mine["version"] == 1
    assert {p: v["level"] for p, v in mine["levels"].items()} == {
        "C1.a": "understand",
        "C1.b": "redo",
        "C1.e": "not-yet",
    }
    assert mine["sent_at"] == sent.json()["sent_at"]


def test_a_level_is_one_of_the_four(ada: TestClient) -> None:
    response = ada.post(SELF, json=c1_levels(a="mastered"))

    assert response.status_code == 422


def test_a_point_not_of_the_competency_is_refused(ada: TestClient) -> None:
    response = ada.post(SELF, json=c1_levels(z="understand"))

    assert response.status_code == 422
    assert "C1.z" in response.json()["detail"]


def test_i_have_done_it_needs_a_github_or_gitlab_link(ada: TestClient) -> None:
    without = ada.post(SELF, json=c1_levels(b="done"))
    elsewhere = ada.post(
        SELF, json=c1_levels(b=("done", "https://example.com/my/work"))
    )
    gitlab = ada.post(
        SELF, json=c1_levels(b=("done", "https://gitlab.com/ada/notes/-/issues/2"))
    )

    assert without.status_code == 422
    assert "link" in without.json()["detail"]
    assert elsewhere.status_code == 422
    assert gitlab.status_code == 200


def test_a_link_is_kept_only_for_i_have_done_it(ada: TestClient) -> None:
    ada.post(SELF, json=c1_levels(a=("understand", LINK), b=("done", LINK)))

    mine = ada.get(PAGE).json()["self_assessment"]["levels"]
    assert mine["C1.a"]["link"] is None
    assert mine["C1.b"]["link"] == LINK


def test_until_the_workspace_closes_every_level_moves_both_ways(
    ada: TestClient,
) -> None:
    ada.post(SELF, json=c1_levels(a="redo", b=("done", LINK)))
    sent = ada.post(SELF, json=c1_levels(a="not-yet", b="understand"))

    assert sent.status_code == 200
    mine = ada.get(PAGE).json()["self_assessment"]
    assert mine["version"] == 2
    assert mine["levels"]["C1.a"]["level"] == "not-yet"
    assert len(mine["history"]) == 2


def test_missed_check_points_ride_with_the_self_assessment_and_show_beside_their_point(
    ada: TestClient,
) -> None:
    ada.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)

    sent = ada.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["oceens-2"]}},
    )

    assert sent.status_code == 200
    page = ada.get(PAGE).json()
    assert next(s for s in page["steps"] if s["id"] == "redraw")[
        "missed_check_points"
    ] == ["oceens-2"]
    hints = points(page)["C1.b"]["missed_check_points"]
    assert [h["id"] for h in hints] == ["oceens-2"]
    assert "OCEENS-CHECK-2" in hints[0]["html"]
    assert points(page)["C1.a"]["missed_check_points"] == []


def test_check_points_before_the_drawing_is_sent_are_refused(ada: TestClient) -> None:
    response = ada.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["oceens-2"]}},
    )

    assert response.status_code == 409


def test_an_unknown_check_point_is_refused(ada: TestClient) -> None:
    ada.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)

    response = ada.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["math-1"]}},
    )

    assert response.status_code == 422


def test_the_latest_ticks_win_whether_sent_alone_or_with_the_self_assessment(
    ada: TestClient,
) -> None:
    ada.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)
    ada.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["oceens-1"]}},
    )
    ada.post(f"{PAGE}/steps/redraw/check-points", json={"missed": ["oceens-3"]})

    redraw = next(s for s in ada.get(PAGE).json()["steps"] if s["id"] == "redraw")
    assert redraw["missed_check_points"] == ["oceens-3"]

    ada.post(SELF, json=c1_levels(a="redo") | {"missed_check_points": {"redraw": []}})
    redraw = next(s for s in ada.get(PAGE).json()["steps"] if s["id"] == "redraw")
    assert redraw["missed_check_points"] == []


def test_a_self_assessment_without_ticks_leaves_the_last_ticks(ada: TestClient) -> None:
    ada.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)
    ada.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["oceens-1"]}},
    )
    ada.post(SELF, json=c1_levels(a="redo"))

    redraw = next(s for s in ada.get(PAGE).json()["steps"] if s["id"] == "redraw")
    assert redraw["missed_check_points"] == ["oceens-1"]


def test_after_the_close_a_level_can_only_move_up_to_i_have_done_it_with_a_link(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = at(make_client, test_settings, future, future)
    before.post(SELF, json=c1_levels(a="understand", b="redo"))
    after = at(make_client, test_settings, past, future)

    down = after.post(SELF, json=c1_levels(a="not-yet", b="redo"))
    sideways = after.post(SELF, json=c1_levels(a="redo", b="redo"))
    up = after.post(SELF, json=c1_levels(a="understand", b=("done", LINK)))

    assert down.status_code == 403
    assert sideways.status_code == 403
    assert "I have done it" in sideways.json()["detail"]
    assert up.status_code == 200
    mine = after.get(PAGE).json()["self_assessment"]
    assert mine["levels"]["C1.b"] == {
        "level": "done",
        "link": LINK,
        "since": up.json()["sent_at"],
    }
    assert mine["levels"]["C1.a"]["level"] == "understand"


@pytest.mark.parametrize("first", ["not-yet", "understand", "redo", ("done", LINK)])
def test_after_the_close_a_point_never_rated_takes_its_first_level_freely(
    make_client: MakeClient,
    test_settings: Settings,
    past: datetime,
    future: datetime,
    first: str | tuple[str, str],
) -> None:
    before = at(make_client, test_settings, future, future)
    before.post(SELF, json=c1_levels(a="understand"))
    after = at(make_client, test_settings, past, future)

    rated = after.post(SELF, json=c1_levels(a="understand", e=first))

    assert rated.status_code == 200
    mine = after.get(PAGE).json()["self_assessment"]
    level, link = first if isinstance(first, tuple) else (first, None)
    assert mine["levels"]["C1.e"] == {
        "level": level,
        "link": link,
        "since": rated.json()["sent_at"],
    }


def test_after_the_close_a_first_level_still_needs_its_link_for_i_have_done_it(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    after = at(make_client, test_settings, past, future)

    assert after.post(SELF, json=c1_levels(e="done")).status_code == 422


def test_after_the_close_a_student_who_never_rated_can_rate_every_point(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    after = at(make_client, test_settings, past, future)

    response = after.post(SELF, json=c1_levels(a="not-yet", b="redo", e=("done", LINK)))

    assert response.status_code == 200


def test_after_the_close_a_point_rated_in_the_window_only_moves_up_to_i_have_done_it(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    after = at(make_client, test_settings, past, future)
    after.post(SELF, json=c1_levels(e="understand"))

    down = after.post(SELF, json=c1_levels(e="not-yet"))
    sideways = after.post(SELF, json=c1_levels(e="redo"))
    dropped = after.post(SELF, json=c1_levels(a="redo"))
    up = after.post(SELF, json=c1_levels(e=("done", LINK)))

    assert down.status_code == 403
    assert sideways.status_code == 403
    assert "I have done it" in sideways.json()["detail"]
    assert dropped.status_code == 403
    assert up.status_code == 200


def test_after_the_close_a_rated_point_cannot_be_dropped(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = at(make_client, test_settings, future, future)
    before.post(SELF, json=c1_levels(a="understand", b="redo"))
    after = at(make_client, test_settings, past, future)

    assert after.post(SELF, json=c1_levels(b=("done", LINK))).status_code == 403


def test_after_the_close_the_ticks_no_longer_change(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = at(make_client, test_settings, future, future)
    before.post(f"{PAGE}/steps/redraw/drawing", json=DRAWING)
    before.post(
        SELF,
        json=c1_levels(a="understand")
        | {"missed_check_points": {"redraw": ["oceens-1"]}},
    )
    after = at(make_client, test_settings, past, future)

    same = after.post(
        SELF,
        json=c1_levels(a=("done", LINK))
        | {"missed_check_points": {"redraw": ["oceens-1"]}},
    )
    other = after.post(
        SELF, json=c1_levels(a=("done", LINK)) | {"missed_check_points": {"redraw": []}}
    )

    assert same.status_code == 200
    assert other.status_code == 403


def test_each_move_is_dated_and_the_levels_unchanged_keep_their_date(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    before = at(make_client, test_settings, future, future)
    first = before.post(SELF, json=c1_levels(a="understand", b="redo")).json()
    after = at(make_client, test_settings, past, future)
    moved = after.post(SELF, json=c1_levels(a="understand", b=("done", LINK))).json()

    mine = after.get(PAGE).json()["self_assessment"]
    assert mine["levels"]["C1.a"]["since"] == first["sent_at"]
    assert mine["levels"]["C1.b"]["since"] == moved["sent_at"]
    assert [v["version"] for v in mine["history"]] == [1, 2]


def test_after_the_reading_day_nothing_changes(
    make_client: MakeClient, test_settings: Settings, past: datetime
) -> None:
    after = at(make_client, test_settings, past, past)

    first = after.post(SELF, json=c1_levels(a="understand"))
    done = after.post(SELF, json=c1_levels(a=("done", LINK)))

    assert first.status_code == 403
    assert done.status_code == 403
    assert "Reading Day" in done.json()["detail"]


def test_the_page_says_both_cut_offs(
    make_client: MakeClient, test_settings: Settings, past: datetime, future: datetime
) -> None:
    page = at(make_client, test_settings, past, future).get(PAGE).json()

    assert page["closed"] is True
    assert page["reading_day_passed"] is False
    assert page["reading_day_at"]
