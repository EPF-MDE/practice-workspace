from __future__ import annotations

import argparse
import sys

from app.course import load_course


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check", help="load a Course folder as the app does at start"
    )
    check.add_argument("folder", help="the Course folder")
    arguments = parser.parse_args(argv)

    problems = load_course(arguments.folder).problems
    for problem in problems:
        print(f"✖ {problem}")
    if problems:
        print(f"{arguments.folder}: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"✔ {arguments.folder}: the Course folder can be served")
    return 0


if __name__ == "__main__":
    sys.exit(main())
