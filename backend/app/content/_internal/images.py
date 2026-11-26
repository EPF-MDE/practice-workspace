from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from markdown_it.token import Token

from .render import IMAGES_FOLDER, markdown

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


def _images_in(tokens: list[Token]) -> Iterator[str]:
    for token in tokens:
        if token.type == "image":
            yield unquote(str(token.attrGet("src") or ""))
        if token.children:
            yield from _images_in(token.children)


def image_problems(text: str, held: Collection[str], where: str) -> list[str]:
    problems: list[str] = []
    for src in _images_in(markdown.parse(text)):
        name = src.removeprefix(f"{IMAGES_FOLDER}/")
        if name == src:
            problems.append(
                f"{where}: the image '{src}' is not in the Course folder's "
                f"{IMAGES_FOLDER}/ folder, the only one images are served from"
            )
        elif name not in held:
            problems.append(
                f"{where}: the Course folder holds no image '{src}' "
                f"({', '.join(IMAGE_TYPES)})"
            )
    return problems
