from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

IMAGES_FOLDER = "images"
IMAGES_URL = "/api/course/images/"

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


@dataclass(frozen=True)
class Image:
    media_type: str
    data: bytes


def read_images(course_folder: Path) -> dict[str, Image]:
    folder = course_folder / IMAGES_FOLDER
    if not folder.is_dir():
        return {}
    return {
        path.relative_to(folder).as_posix(): Image(
            IMAGE_TYPES[path.suffix.lower()], path.read_bytes()
        )
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_TYPES
    }


def _name_in_images(src: str) -> str | None:
    within = src.removeprefix("./").removeprefix(f"{IMAGES_FOLDER}/")
    parts = within.split("/")
    if within == src.removeprefix("./") or "" in parts or ".." in parts:
        return None
    return within


def _image(
    renderer: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
    name = _name_in_images(str(tokens[idx].attrGet("src") or ""))
    if name is not None:
        tokens[idx].attrSet("src", IMAGES_URL + name)
    return renderer.image(tokens, idx, options, env)


markdown = MarkdownIt("commonmark", {"html": False}).enable("table")
markdown.add_render_rule("image", _image)


def _sources_in(tokens: list[Token]) -> Iterator[str]:
    for token in tokens:
        if token.type == "image":
            yield unquote(str(token.attrGet("src") or ""))
        if token.children:
            yield from _sources_in(token.children)


def images_in(
    text: str, held: Collection[str], where: str
) -> tuple[set[str], list[str]]:
    shown: set[str] = set()
    problems: list[str] = []
    for src in _sources_in(markdown.parse(text)):
        name = _name_in_images(src)
        if name is None:
            problems.append(
                f"{where}: the image '{src}' is not in the Course folder's "
                f"{IMAGES_FOLDER}/ folder, the only one images are served from"
            )
        elif name not in held:
            problems.append(
                f"{where}: the Course folder holds no image '{src}' "
                f"({', '.join(IMAGE_TYPES)})"
            )
        else:
            shown.add(name)
    return shown, problems
