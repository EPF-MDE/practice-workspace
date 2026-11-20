"""What loading refuses: anything that could serve what it must not."""

from __future__ import annotations

import re

from ._model import (
    BANDS,
    CHECK_POINTS,
    DRAWING_DIRECTIVES,
    FIELD_KINDS,
    GROUPS,
    INSTRUCTOR_MARKERS,
    LEVELS_BELOW_DONE,
    STEP_KINDS,
    UNVALIDATED_MARKER,
    Answer,
    Canvas,
    ContentError,
    ReferenceDrawing,
    _options,
)
from ._render import Competency, _step_for
from ._tree import _Directive, _RawStep, _walk


def _check(competency: Competency, source: str) -> None:
    step_ids = [s.id for s in competency._steps]
    if len(set(step_ids)) != len(step_ids):
        raise ContentError(f"{source}: two steps share an id")
    point_ids: list[str] = []
    check_points: list[tuple[str, str]] = []  # (where, point id)
    if sum(s.optional for s in competency._steps) > 1:
        raise ContentError(f"{source}: one optional redraw per Competency, not more")
    transfers: list[tuple[str, str]] = []  # (where, the point it fills)
    for index, step in enumerate(competency._steps):
        where = f"{source}, step '{step.id}'"
        directives = list(_walk(step.nodes))
        _check_waiting(competency._steps[:index], step, directives, where)
        if step.kind not in (None, *STEP_KINDS):
            raise ContentError(f"{where}: kind is one of {STEP_KINDS}")
        if step.kind == "transfer":
            if not step.fills:
                raise ContentError(
                    f'{where}: a Transfer says which point\'s "To get there" it fills '
                    "(fills=C1.b)"
                )
            if any(
                "project" not in {f.id for f in _step_for(step, GROUPS[g]).fields}
                for g in GROUPS
            ):
                raise ContentError(
                    f"{where}: a Transfer has a field {{#project}}, the Evidence "
                    "Project by default"
                )
            transfers.append((where, step.fills))
        if step.optional and step.kind != "drawing":
            raise ContentError(f"{where}: only a redraw (kind=drawing) may be optional")
        if step.kind != "drawing" and any(
            d.name in DRAWING_DIRECTIVES for d in directives
        ):
            raise ContentError(f"{where}: drawings belong in a step with kind=drawing")
        groups = {d.name for d in directives if d.name in GROUPS.values()}
        if groups and groups != set(GROUPS.values()):
            raise ContentError(
                f"{where}: has a '{groups.pop()}' block but not the other Group's"
            )
        for d in directives:
            if d.name == "field" and (
                "id" not in d.attrs or d.attrs.get("kind", "line") not in FIELD_KINDS
            ):
                raise ContentError(
                    f"{where}: a field needs {{#id kind=line|text|choice}}"
                )
            if d.name == "field" and (d.attrs.get("kind") == "choice") != (
                "options" in d.attrs
            ):
                raise ContentError(
                    f"{where}: field {d.attrs['id']}: options go with kind=choice, and "
                    "only there"
                )
            if (
                d.name == "field"
                and d.attrs.get("kind") == "choice"
                and len(_options(d.attrs)) < 2
            ):
                raise ContentError(
                    f'{where}: field {d.attrs["id"]} offers at least two options="a|b"'
                )
            if d.name == "point":
                if not re.fullmatch(rf"{competency.id}\.[a-z]", d.attrs.get("id", "")):
                    raise ContentError(
                        f"{where}: a point needs {{#{competency.id}.<letter> band=...}}"
                    )
                if d.attrs.get("band") not in BANDS:
                    raise ContentError(
                        f"{where}: point {d.attrs['id']}'s band is one of {BANDS}"
                    )
                point_ids.append(d.attrs["id"])
                if (
                    sum(
                        isinstance(c, _Directive) and c.name == "proof"
                        for c in d.children
                    )
                    > 1
                ):
                    raise ContentError(
                        f"{where}: point {d.attrs['id']} has one proof sentence, not "
                        "more"
                    )
            if (
                d.name == "to-get-there"
                and d.attrs.get("level") not in LEVELS_BELOW_DONE
            ):
                raise ContentError(
                    f"{where}: to-get-there's level is one of {LEVELS_BELOW_DONE}"
                )
            if d.name in ("field", "answer") and any(
                c.name in ("field", "answer") for c in _walk(d.children)
            ):
                raise ContentError(f"{where}: no field or answer inside a {d.name}")
            if d.name == "reference-drawing":
                inner = [c for c in d.children if isinstance(c, _Directive)]
                if any(c.name != "check-point" for c in _walk(inner)):
                    raise ContentError(
                        f"{where}: a reference-drawing holds check-points only"
                    )
                if len(inner) not in CHECK_POINTS:
                    raise ContentError(
                        f"{where}: a reference-drawing has 3 to 5 check-points, not "
                        f"{len(inner)}"
                    )
                ids = [c.attrs.get("id") for c in inner]
                if None in ids or len(set(ids)) != len(ids):
                    raise ContentError(
                        f"{where}: each check-point needs its own {{#id}}"
                    )
                check_points += [(where, c.attrs.get("point", "")) for c in inner]
        if step.kind == "drawing":
            for group in GROUPS:
                view = _step_for(step, GROUPS[group])
                if view.fields:
                    raise ContentError(
                        f"{where}: a drawing step takes a drawing, not fields"
                    )
                if sum(isinstance(b, Canvas) for b in view.blocks) != 1:
                    raise ContentError(
                        f"{where}: a drawing step has one canvas for {group}"
                    )
                if sum(isinstance(b, ReferenceDrawing) for b in view.blocks) > 1:
                    raise ContentError(
                        f"{where}: one reference-drawing for {group}, not more"
                    )
        for group in GROUPS:
            view = _step_for(step, GROUPS[group])
            ids = [f.id for f in view.fields]
            if len(set(ids)) != len(ids):
                raise ContentError(f"{where}: two fields share an id for {group}")
            # #465 lets a drawing step (kind=drawing) unlock its answer block by the
            # drawing.
            if (
                any(isinstance(b, Answer) for b in view.blocks)
                and not ids
                and step.kind in (None, "answer")
            ):
                raise ContentError(
                    f"{where}: an answer block for {group} but no field to answer in"
                )
    if len(set(point_ids)) != len(point_ids):
        raise ContentError(f"{source}: two points share an id")
    for where, point in transfers:
        if point not in point_ids:
            raise ContentError(
                f"{where}: fills={point}, which is no point of {competency.id}"
            )
    for where, point in check_points:
        if point not in point_ids:
            raise ContentError(
                f"{where}: a check-point's point={point or '?'} is no point of "
                f"{competency.id}"
            )
    for group in GROUPS:
        served = repr(competency.for_group(group))
        for marker in INSTRUCTOR_MARKERS:
            if marker in served.lower():
                raise ContentError(
                    f"{source}: '{marker}' is Instructor Material, never served "
                    f"({group})"
                )
        if UNVALIDATED_MARKER in served:
            raise ContentError(
                f"{source}: '{UNVALIDATED_MARKER}' would be served ({group}): "
                "put it in an HTML comment, beside a blank such as '—'"
            )


def _takes_an_answer(step: _RawStep) -> bool:
    return step.kind == "drawing" or all(
        _step_for(step, g).fields for g in GROUPS.values()
    )


def _check_waiting(
    earlier: tuple[_RawStep, ...],
    step: _RawStep,
    directives: list[_Directive],
    where: str,
) -> None:
    """A step waits for an earlier step that takes an answer, and withholds every field
    it has."""
    waiting = [d for d in directives if d.name == "waiting"]
    if not step.after:
        if waiting:
            raise ContentError(
                f"{where}: a waiting block belongs in a step that waits (after=<step>)"
            )
        return
    before = next((s for s in earlier if s.id == step.after), None)
    if before is None:
        raise ContentError(f"{where}: after={step.after} names no earlier step")
    if not _takes_an_answer(before):
        raise ContentError(
            f"{where}: after={step.after}, a step that takes no answer, so this one "
            "would never open"
        )
    shared = [n for n in step.nodes if isinstance(n, _Directive)]
    nested = [d for top in shared for d in _walk(top.children) if d.name == "waiting"]
    if len(waiting) > 1 or nested:
        raise ContentError(
            f"{where}: one waiting block, outside the Group blocks and any other block"
        )
    if any(
        d.name in ("field", "answer", "canvas", "reference-drawing") for d in shared
    ):
        raise ContentError(
            f"{where}: a step that waits keeps its fields and answers inside the Group "
            "blocks"
        )
