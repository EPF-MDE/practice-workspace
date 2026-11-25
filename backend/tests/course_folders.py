from pathlib import Path

from app.course import COMPETENCIES

ONE_STEP = "## Read {#read minutes=5}\n\nA Step to read.\n"
TWO_GROUPS = (
    '\n[[groups]]\nname = "OcéENS"\nblock = "oceens"\n'
    '\n[[groups]]\nname = "MATHutrice"\nblock = "mathutrice"\n'
)
A_SCALE = (
    '\n[[levels]]\nid = "not-yet"\nlabel = "Not yet"\n'
    '\n[[levels]]\nid = "done"\nlabel = "I have done it"\n'
)


def front_matter(competency: str) -> str:
    return f"---\ncompetency: {competency}\n---\n\n"


def write_course_folder(
    folder: Path,
    content: dict[str, str],
    settings: dict[str, tuple[str, int]] | None = None,
    groups: str = TWO_GROUPS,
) -> Path:
    titled = settings or {c: (f"The title of {c}", 40) for c in COMPETENCIES}
    (folder / "course.toml").write_text(
        'name = "Fixture course"\n'
        + groups
        + "".join(
            f'\n[competencies.{c}]\ntitle = "{title}"\nminutes = {minutes}\n'
            for c, (title, minutes) in titled.items()
        )
        + A_SCALE,
        encoding="utf-8",
    )
    for competency, body in content.items():
        (folder / f"{competency.lower()}.md").write_text(
            front_matter(competency) + body, encoding="utf-8"
        )
    return folder


def with_every_competency(**content: str) -> dict[str, str]:
    return {c: content.get(c, ONE_STEP) for c in COMPETENCIES} | content
