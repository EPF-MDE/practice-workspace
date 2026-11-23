from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from markdown_it import MarkdownIt

from .model import (
    DIRECTIVES,
    Answer,
    Block,
    Canvas,
    CheckPoint,
    ExampleDrawing,
    Field,
    Html,
    Page,
    Point,
    ReferenceDrawing,
    Step,
    Waiting,
    _options,
)
from .tree import _Directive, _Node, _RawStep


@dataclass(frozen=True)
class CompetencyContent:
    id: str
    intro: str
    _steps: tuple[_RawStep, ...]
    groups: dict[str, str] = field(default_factory=dict, hash=False)

    def for_group(self, group: str) -> Page:
        return self._page(self.groups[group])

    def _page(self, block: str | None) -> Page:
        titles = {s.id: s.title for s in self._steps}
        steps = tuple(
            _step_for(s, block, titles.get(s.after or "", "")) for s in self._steps
        )
        return Page(self.id, _render(self.intro), steps)


_markdown = MarkdownIt("commonmark", {"html": False}).enable("table")


def _render(text: str) -> str:
    text = text.strip()
    return _markdown.render(text) if text else ""


def _step_for(step: _RawStep, group: str | None, after_title: str = "") -> Step:
    blocks: list[Block] = []
    _flatten(step.nodes, group, blocks)
    kind = step.kind or (
        "answer" if any(isinstance(b, Field) for b in blocks) else "read"
    )
    waiting: list[Block] = []
    if step.after:
        _flatten(step.nodes, None, waiting)
        waiting = [b for b in waiting if isinstance(b, Html | Waiting)]
        if not any(isinstance(b, Waiting) for b in waiting):
            waiting.append(
                Waiting(
                    _render(
                        f"Send your answer to “{after_title}” first: this step starts "
                        "from it."
                    )
                )
            )
    return Step(
        step.id,
        step.title,
        step.minutes,
        kind,
        step.fills,
        tuple(b for b in blocks if not isinstance(b, Waiting)),
        step.optional,
        step.after,
        tuple(waiting),
    )


def _flatten(nodes: Iterable[_Node], group: str | None, out: list[Block]) -> None:
    pending: list[str] = []

    def flush() -> None:
        html = _render("\n".join(pending))
        pending.clear()
        if html:
            out.append(Html(html))

    for node in nodes:
        if isinstance(node, str):
            pending.append(node)
            continue
        if node.name not in DIRECTIVES:
            if node.name == group:
                flush()
                _flatten(node.children, group, out)
            continue
        flush()
        if node.name == "field":
            out.append(
                Field(
                    node.attrs["id"],
                    node.attrs.get("kind", "line"),
                    _text_html(node.children),
                    _options(node.attrs),
                )
            )
        elif node.name == "answer":
            out.append(Answer(_group_html(node.children, group)))
        elif node.name == "point":
            out.append(_point(node, group))
        elif node.name == "example-drawing":
            out.append(ExampleDrawing(node.snapshot or {}, _text_html(node.children)))
        elif node.name == "canvas":
            out.append(Canvas(_group_html(node.children, group)))
        elif node.name == "reference-drawing":
            check_points = tuple(
                CheckPoint(
                    n.attrs.get("id", ""),
                    n.attrs.get("point", ""),
                    _text_html(n.children),
                )
                for n in node.children
                if isinstance(n, _Directive) and n.name == "check-point"
            )
            out.append(
                ReferenceDrawing(
                    node.snapshot or {}, _text_html(node.children), check_points
                )
            )
        elif node.name == "waiting":
            out.append(Waiting(_text_html(node.children)))
    flush()


def _text_html(nodes: Iterable[_Node]) -> str:
    return _render("\n".join(n for n in nodes if isinstance(n, str)))


def _group_html(nodes: Iterable[_Node], group: str | None) -> str:
    inner: list[Block] = []
    _flatten(nodes, group, inner)
    return "".join(b.html for b in inner if isinstance(b, Html))


def _point(node: _Directive, group: str | None) -> Point:
    statement = [n for n in node.children if isinstance(n, str)]
    proof = next(
        (n for n in node.children if isinstance(n, _Directive) and n.name == "proof"),
        None,
    )
    to_get_there = {
        n.attrs["level"]: _group_html(n.children, group)
        for n in node.children
        if isinstance(n, _Directive) and n.name == "to-get-there"
    }
    return Point(
        node.attrs["id"],
        node.attrs["band"],
        _render("\n".join(statement)),
        _group_html(proof.children, group) if proof else None,
        to_get_there,
    )
