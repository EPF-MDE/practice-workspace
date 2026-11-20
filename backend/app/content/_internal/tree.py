"""A content file, parsed: its steps and their nested directives."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

# --- The parsed file ---------------------------------------------------------


@dataclass
class _Directive:
    name: str
    attrs: dict[str, str]
    children: list[_Node] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None  # a drawing directive's `src`, read


_Node = str | _Directive  # a run of Markdown lines, or a directive


@dataclass(frozen=True)
class _RawStep:
    id: str
    title: str
    minutes: int
    kind: str | None
    fills: str | None
    optional: bool
    after: str | None
    nodes: tuple[_Node, ...]


def _walk(nodes: Iterable[_Node]) -> Iterator[_Directive]:
    for node in nodes:
        if isinstance(node, _Directive):
            yield node
            yield from _walk(node.children)
