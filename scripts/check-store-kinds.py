import ast
import os
import sys
from pathlib import Path

OWNER = Path("backend/app/store")
CONTRACT_SUITE = Path("backend/tests/store_contract")
KIND_ENUM = OWNER / "_internal" / "model.py"
TAKES_A_KIND = {"Kind", "Entry", "latest", "history", "all"}


def kinds(model: str) -> set[str]:
    return {
        node.value.value
        for enum in ast.walk(ast.parse(model))
        if isinstance(enum, ast.ClassDef) and enum.name == "Kind"
        for node in enum.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def called(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def kind_arguments(call: ast.Call) -> list[ast.expr]:
    keyword = [k.value for k in call.keywords if k.arg == "kind"]
    return call.args[:1] + keyword


def literal_kinds(source: str, values: set[str]) -> list[tuple[int, str]]:
    return [
        (argument.lineno, argument.value)
        for call in ast.walk(ast.parse(source))
        if isinstance(call, ast.Call) and called(call) in TAKES_A_KIND
        for argument in kind_arguments(call)
        if isinstance(argument, ast.Constant) and argument.value in values
    ]


def owned(name: str) -> bool:
    path = Path(name)
    return path.is_relative_to(OWNER) or path.is_relative_to(CONTRACT_SUITE)


def main(paths: list[str]) -> int:
    values = kinds(KIND_ENUM.read_text())
    failures = [
        f'{name}:{line}: "{value}"'
        for name in map(os.path.relpath, paths)
        if not owned(name)
        for line, value in literal_kinds(Path(name).read_text(), values)
    ]
    if failures:
        print("These lines write a Store entry kind as a literal:\n", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(
            f"\nName it through the Kind enum that {OWNER} owns, such as Kind.ANSWER.",
            file=sys.stderr,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
