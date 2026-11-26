from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping
from typing import Any

from .check import _check, _served_markers
from .model import (
    DIRECTIVES,
    ContentError,
)
from .render import CompetencyContent
from .tree import _Directive, _Node, _RawStep, _walk

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_STEP = re.compile(r"^## (.+?)\s*\{([^}]*)\}\s*$")
_OPEN = re.compile(r"^:{3,}\s*([A-Za-z][\w-]*)\s*(?:\{([^}]*)\})?\s*$")
_CLOSE = re.compile(r"^:{3,}\s*$")
_FENCE = re.compile(r"^(```|~~~)")
_ATTR = re.compile(r'#([\w.-]+)|([\w-]+)=(?:"([^"]*)"|(\S+))')


def _attrs(text: str | None) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _ATTR.finditer(text or ""):
        if match.group(1):
            attrs["id"] = match.group(1)
        else:
            attrs[match.group(2)] = (
                match.group(3) if match.group(3) is not None else match.group(4)
            )
    return attrs


def _tree(
    lines: list[str], where: str, blocks: Collection[str], problems: list[str]
) -> list[_Node]:
    root = _Directive("", {})
    stack = [root]
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (opened := _OPEN.match(line)):
            name = opened.group(1)
            if name not in DIRECTIVES and name not in blocks:
                problems.append(
                    f"{where}: unknown block '::: {name}', neither a directive nor "
                    "a Group block the Course's settings name"
                )
            directive = _Directive(name, _attrs(opened.group(2)))
            stack[-1].children.append(directive)
            stack.append(directive)
            continue
        elif not fenced and _CLOSE.match(line):
            if len(stack) == 1:
                problems.append(f"{where}: ':::' closes no block")
            else:
                stack.pop()
            continue
        stack[-1].children.append(line)
    problems += [f"{where}: '::: {d.name}' is never closed" for d in stack[1:]]
    return _without_instructor(root.children)


def _without_instructor(nodes: list[_Node]) -> list[_Node]:
    kept: list[_Node] = []
    for node in nodes:
        if isinstance(node, _Directive):
            if node.name == "instructor":
                continue
            node.children = _without_instructor(node.children)
        kept.append(node)
    return kept


Drawings = Callable[[str], dict[str, Any]]


def _no_drawings(src: str) -> dict[str, Any]:
    raise ContentError(f"no folder to read the drawing '{src}' from")


def parse_competency(
    text: str,
    groups: Mapping[str, str],
    source: str = "content",
    drawings: Drawings = _no_drawings,
    *,
    to_get_there_levels: Collection[str] | None,
) -> CompetencyContent:
    clashing = sorted(set(groups.values()) & DIRECTIVES)
    if clashing:
        raise ContentError(
            f"{source}: a Group block is named like a directive: {clashing}"
        )
    text = text.replace("\r\n", "\n")
    front = _FRONT_MATTER.match(text)
    if not front:
        raise ContentError(f"{source}: no front matter (competency:)")
    meta = dict(
        (key.strip(), value.strip())
        for key, _, value in (
            line.partition(":") for line in front.group(1).splitlines()
        )
    )
    if "title" in meta:
        raise ContentError(
            f"{source}: the front matter holds no title: the Course folder's "
            "settings give each Competency its title"
        )
    if not re.fullmatch(r"C\d", meta.get("competency", "")):
        raise ContentError(f"{source}: front matter needs 'competency: C<n>'")
    body = _COMMENT.sub("", text[front.end() :])

    intro: list[str] = []
    steps: list[tuple[str, dict[str, str], list[str]]] = []
    for line in body.split("\n"):
        heading = _STEP.match(line)
        if heading:
            steps.append((heading.group(1), _attrs(heading.group(2)), []))
        else:
            (steps[-1][2] if steps else intro).append(line)

    competency = meta["competency"]
    blocks = set(groups.values())
    problems: list[str] = []
    intro_nodes = _tree(intro, f"{source}, intro", blocks, problems)
    if any(isinstance(n, _Directive) for n in intro_nodes):
        problems.append(f"{source}, intro: blocks belong in a step, not the intro")
    raw_steps: list[_RawStep] = []
    unreadable: set[str] = set()
    for title, attrs, lines in steps:
        where = f"{source}, step '{attrs.get('id', title)}'"
        found = len(problems)
        step = _raw_step(title, attrs, lines, where, blocks, problems)
        if step is None:
            unreadable.add(attrs.get("id", title))
            problems += _served_markers(where, "\n".join(lines), "")
            continue
        for d in _walk(step.nodes):
            if d.name in ("example-drawing", "reference-drawing"):
                d.snapshot = _snapshot(d, drawings, where, problems)
        if len(problems) > found:
            unreadable.add(step.id)
        raw_steps.append(step)
    result = CompetencyContent(
        competency,
        "\n".join(n for n in intro_nodes if isinstance(n, str)),
        tuple(raw_steps),
        dict(groups),
    )
    problems += _check(result, source, to_get_there_levels, unreadable)
    if problems:
        raise ContentError(*dict.fromkeys(problems))
    return result


def _raw_step(
    title: str,
    attrs: dict[str, str],
    lines: list[str],
    where: str,
    blocks: Collection[str],
    problems: list[str],
) -> _RawStep | None:
    if "id" not in attrs or not attrs.get("minutes", "").isdigit():
        problems.append(f"{where}: a step needs {{#id minutes=<n>}}")
        return None
    optional = attrs.get("optional", "no")
    if optional not in ("yes", "no"):
        problems.append(f"{where}: optional is yes or no")
    return _RawStep(
        attrs["id"],
        title,
        int(attrs["minutes"]),
        attrs.get("kind"),
        attrs.get("fills"),
        optional == "yes",
        attrs.get("after"),
        tuple(_tree(lines, where, blocks, problems)),
    )


def _snapshot(
    directive: _Directive, drawings: Drawings, where: str, problems: list[str]
) -> dict[str, Any] | None:
    src = directive.attrs.get("src")
    if not src:
        problems.append(
            f"{where}: '{directive.name}' needs {{src=<a tldraw snapshot>}}"
        )
        return None
    try:
        snapshot = drawings(src)
    except (KeyError, OSError, ValueError) as error:
        problems.append(f"{where}: cannot read the drawing '{src}': {error}")
        return None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("document"), dict):
        problems.append(
            f"{where}: '{src}' is not a tldraw snapshot ({{document, session}})"
        )
        return None
    return snapshot
