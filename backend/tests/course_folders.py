import subprocess
import sys
from pathlib import Path

from conftest import FIXTURE_CLOSE, FIXTURE_READING_DAY, FIXTURE_TIME_ZONE

from app.course import COMPETENCIES
from app.settings import Settings

ONE_STEP = "## Read {#read minutes=5}\n\nA Step to read.\n"
TWO_GROUPS = (
    '\n[[groups]]\nname = "OcéENS"\nblock = "oceens"\n'
    '\n[[groups]]\nname = "MATHutrice"\nblock = "mathutrice"\n'
)
A_SCALE = (
    '\n[[levels]]\nid = "not-yet"\nlabel = "Not yet"\n'
    '\n[[levels]]\nid = "done"\nlabel = "I have done it"\n'
)

CALENDAR = (
    f'\n[calendar]\ntime_zone = "{FIXTURE_TIME_ZONE.key}"\n'
    f"close = {FIXTURE_CLOSE.replace(tzinfo=None).isoformat()}\n"
    f"reading_day = {FIXTURE_READING_DAY.replace(tzinfo=None).isoformat()}\n"
)


def on(test_settings: Settings, folder: Path) -> Settings:
    return test_settings.model_copy(update={"course_folder": str(folder)})


def front_matter(competency: str) -> str:
    return f"---\ncompetency: {competency}\n---\n\n"


def write_course_folder(
    folder: Path,
    content: dict[str, str],
    settings: dict[str, tuple[str, int]] | None = None,
    groups: str = TWO_GROUPS,
    read_when_none_declared: str = "roster",
) -> Path:
    titled = settings or {c: (f"The title of {c}", 40) for c in COMPETENCIES}
    (folder / "course.toml").write_text(
        'name = "Fixture course"\n'
        + f'read_when_none_declared = "{read_when_none_declared}"\n'
        + groups
        + "".join(
            f'\n[competencies.{c}]\ntitle = "{title}"\nminutes = {minutes}\n'
            for c, (title, minutes) in titled.items()
        )
        + A_SCALE
        + CALENDAR,
        encoding="utf-8",
    )
    for competency, body in content.items():
        (folder / f"{competency.lower()}.md").write_text(
            front_matter(competency) + body, encoding="utf-8"
        )
    return folder


def with_every_competency(**content: str) -> dict[str, str]:
    return {c: content.get(c, ONE_STEP) for c in COMPETENCIES} | content


BACKEND = Path(__file__).resolve().parents[1]


def verify(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app", "verify", str(folder)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )


def problems(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("✖")]
