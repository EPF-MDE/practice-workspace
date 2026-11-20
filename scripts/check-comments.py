import ast
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

BASELINE = Path("lint-rules/comments-baseline.json")
PYTHON_DIRECTIVE = re.compile(r"#\s*(noqa|type:\s*ignore|pragma|fmt:|ruff:|mypy:)")
SHELL_DIRECTIVE = re.compile(r"#\s*shellcheck ")
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def python_comments(source: str) -> int:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    hashes = sum(
        1
        for token in tokens
        if token.type == tokenize.COMMENT and not PYTHON_DIRECTIVE.match(token.string)
    )
    docstrings = sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, DOCSTRING_OWNERS) and ast.get_docstring(node) is not None
    )
    return hashes + docstrings


def shell_comments(source: str) -> int:
    lines = source.splitlines()
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]
    return sum(
        1
        for line in lines
        if line.lstrip().startswith("#") and not SHELL_DIRECTIVE.match(line.lstrip())
    )


def count(path: Path) -> int:
    source = path.read_text()
    return python_comments(source) if path.suffix == ".py" else shell_comments(source)


def main(paths: list[str]) -> int:
    baseline: dict[str, int] = (
        json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    )
    failures = [
        f"{entry}: in {BASELINE}, and no such file: remove its entry."
        for entry in baseline
        if not Path(entry).exists()
    ]
    for name in map(os.path.relpath, paths):
        found, allowed = count(Path(name)), baseline.get(name, 0)
        if found > allowed:
            failures.append(
                f"{name}: {found} comments, and it may hold {allowed}. Delete the"
                " comment: a name says what, an ADR in docs/adr/ says why. See"
                " CODING_STANDARDS.md, A decision lives in an ADR, not a comment."
            )
        elif found < allowed:
            failures.append(
                f"{name}: {found} comments, fewer than the {allowed} {BASELINE}"
                f" allows: lower its entry to {found}, or remove it at 0."
            )
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
