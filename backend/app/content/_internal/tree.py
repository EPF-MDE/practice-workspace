from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .model import DIRECTIVES


@dataclass
class _Directive:
    name: str
    attrs: dict[str, str]
    children: list[_Node] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None

    @property
    def is_group_block(self) -> bool:
        return self.name not in DIRECTIVES


_Node = str | _Directive


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
