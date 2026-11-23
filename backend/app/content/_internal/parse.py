from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping
from typing import Any, cast

from .check import _check
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


def _tree(lines: list[str], where: str, blocks: Collection[str]) -> list[_Node]:
    root = _Directive("", {})
    stack = [root]
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (opened := _OPEN.match(line)):
            name = opened.group(1)
            if name not in DIRECTIVES and name not in blocks:
                raise ContentError(
                    f"{where}: unknown block '::: {name}', neither a directive nor "
                    "the block of a Group in the Course's settings"
                )
            directive = _Directive(name, _attrs(opened.group(2)))
            stack[-1].children.append(directive)
            stack.append(directive)
            continue
        elif not fenced and _CLOSE.match(line):
            if len(stack) == 1:
                raise ContentError(f"{where}: ':::' closes no block")
            stack.pop()
            continue
        stack[-1].children.append(line)
    if len(stack) > 1:
        raise ContentError(f"{where}: '::: {stack[-1].name}' is never closed")
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
            f"{source}: a Group's block is named like a directive: {clashing}"
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
    intro_nodes = _tree(intro, f"{source}, intro", blocks)
    if any(isinstance(n, _Directive) for n in intro_nodes):
        raise ContentError(f"{source}: blocks belong in a step, not the intro")
    raw_steps = tuple(
        _raw_step(title, attrs, lines, source, blocks) for title, attrs, lines in steps
    )
    for step in raw_steps:
        for d in _walk(step.nodes):
            if d.name in ("example-drawing", "reference-drawing"):
                d.snapshot = _snapshot(d, drawings, f"{source}, step '{step.id}'")
    result = CompetencyContent(
        competency,
        "\n".join(cast(list[str], intro_nodes)),
        raw_steps,
        dict(groups),
    )
    _check(result, source, to_get_there_levels)
    return result


def _raw_step(
    title: str,
    attrs: dict[str, str],
    lines: list[str],
    source: str,
    blocks: Collection[str],
) -> _RawStep:
    where = f"{source}, step '{title}'"
    if "id" not in attrs or not attrs.get("minutes", "").isdigit():
        raise ContentError(f"{where}: a step needs {{#id minutes=<n>}}")
    optional = attrs.get("optional", "no")
    if optional not in ("yes", "no"):
        raise ContentError(f"{where}: optional is yes or no")
    return _RawStep(
        attrs["id"],
        title,
        int(attrs["minutes"]),
        attrs.get("kind"),
        attrs.get("fills"),
        optional == "yes",
        attrs.get("after"),
        tuple(_tree(lines, where, blocks)),
    )


def _snapshot(directive: _Directive, drawings: Drawings, where: str) -> dict[str, Any]:
    src = directive.attrs.get("src")
    if not src:
        raise ContentError(
            f"{where}: '{directive.name}' needs {{src=<a tldraw snapshot>}}"
        )
    try:
        snapshot = drawings(src)
    except (KeyError, OSError, ValueError) as error:
        raise ContentError(
            f"{where}: cannot read the drawing '{src}': {error}"
        ) from error
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("document"), dict):
        raise ContentError(
            f"{where}: '{src}' is not a tldraw snapshot ({{document, session}})"
        )
    return snapshot
