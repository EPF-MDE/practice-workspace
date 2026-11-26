from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from typing import NamedTuple

from .model import (
    BANDS,
    CHECK_POINTS_PER_REFERENCE_DRAWING,
    DRAWING_DIRECTIVES,
    FIELD_KINDS,
    INSTRUCTOR_MARKERS,
    STEP_KINDS,
    UNVALIDATED_MARKER,
    Answer,
    Canvas,
    ReferenceDrawing,
    _options,
)
from .render import CompetencyContent, _render, _step_for
from .tree import _Directive, _Node, _RawStep, _walk


class _PointAt(NamedTuple):
    where: str
    point: str


def _check(
    competency: CompetencyContent,
    source: str,
    to_get_there_levels: Collection[str] | None,
    unreadable: set[str],
) -> list[str]:
    problems: list[str] = []
    steps = competency._steps
    group_blocks = competency.groups
    shared_ids = Counter(s.id for s in steps)
    problems += [
        f"{source}, step '{id}': {count} steps share this id"
        for id, count in shared_ids.items()
        if count > 1
    ]
    optional = [s.id for s in steps if s.optional]
    if len(optional) > 1:
        problems.append(
            f"{source}, steps {', '.join(optional)}: one optional redraw per "
            "Competency, not more"
        )
    points: list[_PointAt] = []
    transfers: list[_PointAt] = []
    check_points: list[_PointAt] = []
    for index, step in enumerate(steps):
        where = f"{source}, step '{step.id}'"
        _check_waiting(steps[:index], step, where, group_blocks, unreadable, problems)
        if step.kind not in (None, *STEP_KINDS):
            problems.append(f"{where}: kind is one of {STEP_KINDS}")
        if step.optional and step.kind != "drawing":
            problems.append(f"{where}: only a redraw (kind=drawing) may be optional")
        if step.kind == "transfer" and not step.fills:
            problems.append(
                f'{where}: a Transfer says which point\'s "To get there" it fills '
                "(fills=C1.b)"
            )
        elif step.kind == "transfer" and step.fills:
            transfers.append(_PointAt(where, step.fills))
        found = len(problems)
        _check_directives(
            competency.id,
            step,
            where,
            to_get_there_levels,
            points,
            check_points,
            problems,
        )
        if len(problems) > found:
            unreadable.add(step.id)
        if step.id in unreadable:
            problems += _served_markers(where, _text(step.nodes), "")
            continue
        _check_views(step, where, group_blocks, problems)
    point_ids: set[str] = set()
    for where, point in points:
        if point in point_ids:
            problems.append(f"{where}: point {point} shares its id with an earlier one")
        point_ids.add(point)
    problems += [
        f"{where}: fills={point}, which is no point of {competency.id}"
        for where, point in transfers
        if point not in point_ids
    ]
    problems += [
        f"{where}: a check-point's point={point or '?'} is no point of {competency.id}"
        for where, point in check_points
        if point not in point_ids
    ]
    problems += _served_markers(f"{source}, intro", _render(competency.intro), "")
    return problems


def _check_directives(
    competency: str,
    step: _RawStep,
    where: str,
    to_get_there_levels: Collection[str] | None,
    points: list[_PointAt],
    check_points: list[_PointAt],
    problems: list[str],
) -> None:
    directives = list(_walk(step.nodes))
    if step.kind != "drawing" and any(d.name in DRAWING_DIRECTIVES for d in directives):
        problems.append(f"{where}: drawings belong in a step with kind=drawing")
    for d in directives:
        if d.name == "field" and (
            "id" not in d.attrs or d.attrs.get("kind", "line") not in FIELD_KINDS
        ):
            problems.append(f"{where}: a field needs {{#id kind=line|text|choice}}")
            continue
        if d.name == "field" and (d.attrs.get("kind") == "choice") != (
            "options" in d.attrs
        ):
            problems.append(
                f"{where}: field {d.attrs['id']}: options go with kind=choice, and "
                "only there"
            )
        elif (
            d.name == "field"
            and d.attrs.get("kind") == "choice"
            and len(_options(d.attrs)) < 2
        ):
            problems.append(
                f'{where}: field {d.attrs["id"]} offers at least two options="a|b"'
            )
        if d.name == "point":
            if not re.fullmatch(rf"{competency}\.[a-z]", d.attrs.get("id", "")):
                problems.append(
                    f"{where}: a point needs {{#{competency}.<letter> band=...}}"
                )
                continue
            if d.attrs.get("band") not in BANDS:
                problems.append(
                    f"{where}: point {d.attrs['id']}'s band is one of {BANDS}"
                )
            points.append(_PointAt(where, d.attrs["id"]))
            proofs = [
                c for c in d.children if isinstance(c, _Directive) and c.name == "proof"
            ]
            if len(proofs) > 1:
                problems.append(
                    f"{where}: point {d.attrs['id']} has one proof sentence, not more"
                )
        if d.name == "to-get-there" and to_get_there_levels is None:
            if "level" not in d.attrs:
                problems.append(f"{where}: a to-get-there needs a level=<level>")
        elif d.name == "to-get-there" and (
            d.attrs.get("level") not in (to_get_there_levels or ())
        ):
            problems.append(
                f"{where}: to-get-there's level={d.attrs.get('level', '?')} is "
                "not one of the Course's levels below the top: "
                f"{', '.join(to_get_there_levels or ())}"
            )
        if d.name in ("field", "answer") and any(
            c.name in ("field", "answer") for c in _walk(d.children)
        ):
            problems.append(f"{where}: no field or answer inside a {d.name}")
        if d.name == "reference-drawing":
            _check_reference(d, where, check_points, problems)


def _check_reference(
    d: _Directive,
    where: str,
    check_points: list[_PointAt],
    problems: list[str],
) -> None:
    inner = [c for c in d.children if isinstance(c, _Directive)]
    if any(c.name != "check-point" for c in _walk(inner)):
        problems.append(f"{where}: a reference-drawing holds check-points only")
    if len(inner) not in CHECK_POINTS_PER_REFERENCE_DRAWING:
        fewest = min(CHECK_POINTS_PER_REFERENCE_DRAWING)
        most = max(CHECK_POINTS_PER_REFERENCE_DRAWING)
        problems.append(
            f"{where}: a reference-drawing has {fewest} to {most} check-points, "
            f"not {len(inner)}"
        )
    ids = [c.attrs.get("id") for c in inner]
    if None in ids or len(set(ids)) != len(ids):
        problems.append(f"{where}: each check-point needs its own {{#id}}")
    check_points += [_PointAt(where, c.attrs.get("point", "")) for c in inner]


GROUP_NAMES_SLOT = "\0"


def _check_views(
    step: _RawStep, where: str, group_blocks: Mapping[str, str], problems: list[str]
) -> None:
    blocks = {d.name for d in _walk(step.nodes) if d.is_group_block}
    missing = [name for name, block in group_blocks.items() if block not in blocks]
    if blocks and missing:
        problems.append(f"{where}: has a Group block but none for {', '.join(missing)}")
    groups_by_problem: dict[str, list[str]] = {}
    for group, block in group_blocks.items():
        for problem in _view_problems(step, block, where):
            groups_by_problem.setdefault(problem, []).append(group)
    problems += [
        problem.replace(GROUP_NAMES_SLOT, ", ".join(groups))
        for problem, groups in groups_by_problem.items()
    ]


def _view_problems(step: _RawStep, block: str, where: str) -> list[str]:
    problems: list[str] = []
    view = _step_for(step, block)
    ids = [f.id for f in view.fields]
    if step.kind == "transfer" and "project" not in ids:
        problems.append(
            f"{where}: a Transfer has a field {{#project}}, the Evidence "
            f"Project by default ({GROUP_NAMES_SLOT})"
        )
    if step.kind == "drawing":
        if view.fields:
            problems.append(f"{where}: a drawing step takes a drawing, not fields")
        if sum(isinstance(b, Canvas) for b in view.blocks) != 1:
            problems.append(
                f"{where}: a drawing step has one canvas for {GROUP_NAMES_SLOT}"
            )
        if sum(isinstance(b, ReferenceDrawing) for b in view.blocks) > 1:
            problems.append(
                f"{where}: one reference-drawing for {GROUP_NAMES_SLOT}, not more"
            )
    if len(set(ids)) != len(ids):
        problems.append(f"{where}: two fields share an id for {GROUP_NAMES_SLOT}")
    if (
        any(isinstance(b, Answer) for b in view.blocks)
        and not ids
        and step.kind in (None, "answer")
    ):
        problems.append(
            f"{where}: an answer block for {GROUP_NAMES_SLOT} but no field to answer in"
        )
    return problems + _served_markers(where, repr(view), f" ({GROUP_NAMES_SLOT})")


def _text(nodes: Iterable[_Node]) -> str:
    return "\n".join(
        node
        if isinstance(node, str)
        else " ".join([*node.attrs.values(), _text(node.children)])
        for node in nodes
    )


def _served_markers(where: str, served: str, group: str) -> list[str]:
    problems = [
        f"{where}: '{marker}' is Instructor Material, never served{group}"
        for marker in INSTRUCTOR_MARKERS
        if marker in served.lower()
    ]
    if UNVALIDATED_MARKER in served:
        problems.append(
            f"{where}: '{UNVALIDATED_MARKER}' would be served{group}: "
            "put it in an HTML comment, beside a blank such as '—'"
        )
    return problems


def _takes_an_answer(step: _RawStep, group_blocks: Mapping[str, str]) -> bool:
    return step.kind == "drawing" or all(
        _step_for(step, block).fields for block in group_blocks.values()
    )


def _check_waiting(
    earlier: tuple[_RawStep, ...],
    step: _RawStep,
    where: str,
    group_blocks: Mapping[str, str],
    unreadable: Collection[str],
    problems: list[str],
) -> None:
    waiting = [d for d in _walk(step.nodes) if d.name == "waiting"]
    if not step.after:
        if waiting:
            problems.append(
                f"{where}: a waiting block belongs in a step that waits (after=<step>)"
            )
        return
    before = next((s for s in earlier if s.id == step.after), None)
    if before is None and step.after not in unreadable:
        problems.append(f"{where}: after={step.after} names no earlier step")
    elif (
        before
        and before.id not in unreadable
        and not _takes_an_answer(before, group_blocks)
    ):
        problems.append(
            f"{where}: after={step.after}, a step that takes no answer, so this one "
            "would never open"
        )
    shared = [n for n in step.nodes if isinstance(n, _Directive)]
    nested = [d for top in shared for d in _walk(top.children) if d.name == "waiting"]
    if len(waiting) > 1 or nested:
        problems.append(
            f"{where}: one waiting block, outside the Group blocks and any other block"
        )
    if any(
        d.name in ("field", "answer", "canvas", "reference-drawing") for d in shared
    ):
        problems.append(
            f"{where}: a step that waits keeps its fields and answers inside the Group "
            "blocks"
        )
