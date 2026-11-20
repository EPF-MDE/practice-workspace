"""The content format: what the loader refuses, so nothing it must not serve is served.

Through `parse_competency`, the content module's interface.
"""

from pathlib import Path

import pytest

from app.content import Competency, ContentError, Html, Waiting, parse_competency

HEAD = "---\ncompetency: C1\ntitle: T\n---\n\n"


def parse(body: str) -> Competency:
    return parse_competency(HEAD + body)


@pytest.mark.parametrize(
    "body",
    [
        # a typo would serve the answer as text
        "## S {#s minutes=5}\n\n::: answr\nx\n:::\n",
        "## S {#s minutes=5}\n\n::: answer\nx\n",  # never closed
        "## S {#s minutes=5}\n\n:::\n",  # closes nothing
        # an answer with no field to unlock it
        "## S {#s minutes=5}\n\n::: answer\nx\n:::\n",
        "## S {#s minutes=5}\n\n::: oceens\nx\n:::\n",  # one Group's block only
        "## S {#s minutes=5}\n\nRead the Banding Anchors.\n",
        "## S {#s}\n\nx\n",  # no timing
        "## S {#s minutes=5}\n\n## T {#s minutes=5}\n",  # two steps, one id
        "## S {#s minutes=5}\n\n::: point {#C1.a band=Great}\nx\n:::\n",
    ],
)
def test_the_loader_refuses(body: str) -> None:
    with pytest.raises(ContentError):
        parse(body)


@pytest.mark.parametrize(
    "body",
    [
        "## S {#s minutes=5}\n\nRequests a day: TO VALIDATE.\n",
        "## S {#s minutes=5}\n\n::: field {#f}\nx\n:::\n\n"
        "::: answer\n| a | b |\n|---|---|\n| 1 | TO VALIDATE |\n:::\n",
    ],
)
def test_a_figure_waiting_on_validation_is_never_served_not_even_in_an_answer(
    body: str,
) -> None:
    with pytest.raises(ContentError, match="TO VALIDATE"):
        parse(body)


def test_a_figure_waiting_on_validation_stays_in_an_html_comment_beside_a_blank() -> (
    None
):
    page = parse(
        "## S {#s minutes=5}\n\nRequests a day: — <!-- TO VALIDATE: the requests -->\n"
    ).for_group("OcéENS")

    assert "TO VALIDATE" not in repr(page)
    block = page.steps[0].blocks[0]
    assert isinstance(block, Html)
    assert "Requests a day: —" in block.html


def test_a_code_fence_may_show_a_directive() -> None:
    page = parse("## S {#s minutes=5}\n\n```\n::: answer\n```\n").for_group("OcéENS")

    block = page.steps[0].blocks[0]
    assert isinstance(block, Html)
    assert "::: answer" in block.html


def test_authoring_notes_are_stripped() -> None:
    page = parse(
        "<!-- NOTE-1 -->\n## S {#s minutes=5}\n\n::: instructor\nNOTE-2\n:::\n\nText.\n"
    ).for_group("MATHutrice")

    assert "NOTE" not in repr(page)


# --- Drawing steps (#465) ----------------------------------------------------

SNAPSHOTS = {
    "example.json": {
        "document": {"store": {"shape:a": {"id": "shape:a"}}, "schema": {}}
    },
    "oceens.json": {
        "document": {"store": {"shape:o": {"id": "shape:o"}}, "schema": {}}
    },
    "math.json": {"document": {"store": {"shape:m": {"id": "shape:m"}}, "schema": {}}},
}


def check_points(n: int, point: str = "C1.a") -> str:
    return "".join(
        f"::: check-point {{#cp-{i} point={point}}}\nCheck point {i}.\n:::\n"
        for i in range(n)
    )


def drawing_step(
    oceens_points: int = 3,
    head: str = "{#redraw minutes=10 kind=drawing}",
    point: str = "C1.a",
) -> str:
    return (
        f"## Redraw {head}\n\n"
        "::: example-drawing {src=example.json}\nA simpler system, drawn.\n:::\n\n"
        "::: oceens\n::: canvas\nFrom the click to the summary.\n:::\n\n"
        "::: reference-drawing {src=oceens.json}\nThe OcéENS chain.\n\n"
        f"{check_points(oceens_points, point)}:::\n:::\n\n"
        "::: mathutrice\n::: canvas\nFrom the button to the test.\n:::\n\n"
        "::: reference-drawing {src=math.json}\nThe MATHutrice chain.\n\n"
        f"{check_points(3, point)}:::\n:::\n"
    )


CLOSING = (
    "## Close {#closing minutes=0 kind=closing}\n\n"
    "::: point {#C1.a band=Basic}\nA.\n:::\n"
)


def parse_drawing(body: str) -> Competency:
    return parse_competency(HEAD + body, drawings=lambda src: SNAPSHOTS[src])


def test_a_drawing_step_has_an_example_a_canvas_and_a_reference_with_its_check_points() -> (  # noqa: E501
    None
):
    from app.content import Canvas, ExampleDrawing, ReferenceDrawing

    step = parse_drawing(drawing_step() + CLOSING).for_group("OcéENS").steps[0]

    assert step.kind == "drawing" and not step.optional
    example, canvas, reference = (b for b in step.blocks if not hasattr(b, "html"))
    assert (
        isinstance(example, ExampleDrawing)
        and example.snapshot == SNAPSHOTS["example.json"]
    )
    assert "simpler system" in example.caption_html
    assert isinstance(canvas, Canvas) and "From the click" in canvas.prompt_html
    assert (
        isinstance(reference, ReferenceDrawing)
        and reference.snapshot == SNAPSHOTS["oceens.json"]
    )
    assert "OcéENS chain" in reference.caption_html
    assert [(c.id, c.point) for c in reference.check_points] == [
        ("cp-0", "C1.a"),
        ("cp-1", "C1.a"),
        ("cp-2", "C1.a"),
    ]
    assert "Check point 1." in reference.check_points[1].html


def test_a_group_receives_its_own_reference_drawing() -> None:
    step = parse_drawing(drawing_step() + CLOSING).for_group("MATHutrice").steps[0]

    assert step.reference is not None
    assert step.reference.snapshot == SNAPSHOTS["math.json"]
    assert "MATHutrice chain" in step.reference.caption_html


def test_one_redraw_per_competency_may_be_optional() -> None:
    step = parse_drawing(
        drawing_step(head="{#more minutes=0 kind=drawing optional=yes}") + CLOSING
    )

    assert step.for_group("OcéENS").steps[0].optional


@pytest.mark.parametrize(
    "body",
    [
        drawing_step(oceens_points=2) + CLOSING,  # fewer than 3 check points
        drawing_step(oceens_points=6) + CLOSING,  # more than 5
        drawing_step(point="C1.z")
        + CLOSING,  # a check point beside no point of the review
        drawing_step().replace("kind=drawing", "kind=answer")
        + CLOSING,  # a canvas outside a drawing step
        drawing_step().replace("::: canvas\nFrom the click to the summary.\n:::\n", "")
        + CLOSING,  # no canvas
        drawing_step().replace("src=example.json", "src=missing.json")
        + CLOSING,  # a drawing that isn't there
        drawing_step(head="{#a minutes=0 kind=drawing optional=yes}")
        + drawing_step(head="{#b minutes=0 kind=drawing optional=yes}")
        + CLOSING,  # two optional redraws
        "## S {#s minutes=5 optional=yes}\n\n::: field {#f}\nx\n:::\n"
        + CLOSING,  # optional, but not a redraw
    ],
)
def test_the_loader_refuses_a_drawing_step(body: str) -> None:
    with pytest.raises(ContentError):
        parse_drawing(body)


def test_a_drawing_is_read_from_the_content_folder_and_never_outside_it(
    tmp_path: Path,
) -> None:
    import json

    from app.content import load_content

    (tmp_path / "drawings").mkdir()
    for name, snapshot in SNAPSHOTS.items():
        (tmp_path / "drawings" / name).write_text(json.dumps(snapshot))
    text = HEAD + drawing_step().replace("src=", "src=drawings/") + CLOSING
    (tmp_path / "c1.md").write_text(text)

    reference = load_content(tmp_path)["C1"].for_group("OcéENS").steps[0].reference
    assert reference is not None
    assert reference.snapshot == SNAPSHOTS["oceens.json"]

    (tmp_path / "c1.md").write_text(
        text.replace("src=drawings/example.json", "src=../c1.md")
    )
    with pytest.raises(ContentError):
        load_content(tmp_path)


# --- The closing step and the Transfer (#466) --------------------------------

TRANSFER = (
    "## Transfer {#transfer minutes=5 kind=transfer fills=C1.a}\n\n"
    "::: field {#project}\nThe project\n:::\n\n"
    "::: field {#plan kind=text}\nYour plan\n:::\n\n"
)


def test_a_transfer_names_the_point_whose_to_get_there_it_fills() -> None:
    step = parse(TRANSFER + CLOSING).for_group("OcéENS").steps[0]

    assert (step.kind, step.fills) == ("transfer", "C1.a")


@pytest.mark.parametrize(
    "body",
    [
        TRANSFER.replace(" fills=C1.a", "") + CLOSING,  # fills no point
        TRANSFER.replace("fills=C1.a", "fills=C1.z")
        + CLOSING,  # fills a point the review doesn't have
        TRANSFER.replace("{#project}", "{#where}")
        + CLOSING,  # no project field: the Evidence Project is its default
        "## S {#s minutes=5 kind=closng}\n\nx\n",  # a kind no step has
        CLOSING.replace(
            "::: point {#C1.a band=Basic}\nA.\n",
            "::: point {#C1.a band=Basic}\nA.\n\n"
            "::: proof\nOne.\n:::\n\n::: proof\nTwo.\n:::\n",
        ),  # two proof sentences
    ],
)
def test_the_loader_refuses_a_transfer_or_closing_step(body: str) -> None:
    with pytest.raises(ContentError):
        parse(body)


# --- Choice fields (#470) ----------------------------------------------------


def test_a_choice_field_offers_its_options_in_order() -> None:
    page = parse(
        "## S {#s minutes=5}\n\n"
        '::: field {#red kind=choice options="none|architecture|test"}\n'
        "Which job goes red?\n:::\n"
    ).for_group("OcéENS")

    (field,) = page.steps[0].fields
    assert (field.kind, field.options) == ("choice", ("none", "architecture", "test"))
    assert "Which job goes red?" in field.label_html


@pytest.mark.parametrize(
    "attrs",
    [
        "kind=choice",  # no options to choose from
        'kind=choice options="only"',  # one option is no choice
        'kind=line options="a|b"',  # options on a field that cannot show them
    ],
)
def test_the_loader_refuses_a_choice_field_without_two_options(attrs: str) -> None:
    with pytest.raises(ContentError):
        parse(f"## S {{#s minutes=5}}\n\n::: field {{#f {attrs}}}\nPick.\n:::\n")


RANK = "## Rank {#rank minutes=5}\n\n::: field {#ranking}\nYour ranking.\n:::\n\n"
GROUP_FIELDS = (
    "::: oceens\n::: field {#f}\nO.\n:::\n:::\n\n"
    "::: mathutrice\n::: field {#f}\nM.\n:::\n:::\n"
)


def test_a_step_that_waits_serves_its_shared_part_and_the_marker_until_then() -> None:
    page = parse(
        RANK + "## Fix {#fix minutes=5 after=rank}\n\nThe Worked Example.\n\n"
        "::: waiting\nSend your ranking first.\n:::\n\n" + GROUP_FIELDS
    ).for_group("OcéENS")

    fix = page.step("fix")
    assert fix is not None
    assert fix.after == "rank"
    assert [f.id for f in fix.fields] == ["f"]
    assert "Send your ranking first" not in repr(fix.blocks)
    assert ["Worked Example" in getattr(b, "html", "") for b in fix.waiting] == [
        True,
        False,
    ]
    marker = fix.waiting[-1]
    assert isinstance(marker, Waiting)
    assert "Send your ranking first" in marker.html
    assert "O." not in repr(fix.waiting)


@pytest.mark.parametrize(
    "body",
    [
        RANK
        + "## Fix {#fix minutes=5 after=nowhere}\n\n"
        + GROUP_FIELDS,  # an unknown step
        "## Fix {#fix minutes=5 after=rank}\n\n"
        + GROUP_FIELDS
        + "\n"
        + RANK,  # a later step
        RANK + "## Fix {#fix minutes=5 after=fix}\n\n" + GROUP_FIELDS,  # itself
        "## Rank {#rank minutes=5}\n\nRead.\n\n## Fix {#fix minutes=5 after=rank}\n\n"
        + GROUP_FIELDS,  # no answer
        RANK
        # a field it can't withhold
        + "## Fix {#fix minutes=5 after=rank}\n\n::: field {#f}\nShared.\n:::\n",
        RANK
        + "## Fix {#fix minutes=5}\n\n::: waiting\nx\n:::\n\n"
        + GROUP_FIELDS,  # a marker in a step that waits for none
    ],
)
def test_the_loader_refuses_a_step_that_waits(body: str) -> None:
    with pytest.raises(ContentError):
        parse(body)
