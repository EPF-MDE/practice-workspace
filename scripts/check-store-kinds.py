import ast
import os
import sys
from pathlib import Path

OWNER = Path("backend/app/store")
CONTRACT_SUITE = Path("backend/tests/store_contract")
KIND = "Kind"


def store_sources() -> list[ast.Module]:
    return [ast.parse(path.read_text()) for path in sorted(OWNER.rglob("*.py"))]


def kind_values(modules: list[ast.Module]) -> set[str]:
    return {
        node.value.value
        for module in modules
        for enum in ast.walk(module)
        if isinstance(enum, ast.ClassDef) and enum.name == KIND
        for node in enum.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def is_kind(annotation: ast.expr | None) -> bool:
    return isinstance(annotation, ast.Name) and annotation.id == KIND


def kind_position(names: list[tuple[str, ast.expr | None]]) -> int | None:
    found = [i for i, (_, annotation) in enumerate(names) if is_kind(annotation)]
    return found[0] if found else None


def parameters(function: ast.FunctionDef) -> list[tuple[str, ast.expr | None]]:
    params = [(a.arg, a.annotation) for a in function.args.args]
    return params[1:] if params and params[0][0] in ("self", "cls") else params


def fields(dataclass: ast.ClassDef) -> list[tuple[str, ast.expr | None]]:
    return [
        (node.target.id, node.annotation)
        for node in dataclass.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]


def takes_a_kind(modules: list[ast.Module]) -> dict[str, int]:
    takers = {KIND: 0}
    for module in modules:
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef):
                position = kind_position(parameters(node))
            elif isinstance(node, ast.ClassDef) and node.name != KIND:
                position = kind_position(fields(node))
            else:
                continue
            if position is not None:
                takers[node.name] = position
    return takers


def callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def kind_arguments(call: ast.Call, position: int) -> list[ast.expr]:
    keyword = [k.value for k in call.keywords if k.arg == "kind"]
    return call.args[position : position + 1] + keyword


def literal_kinds(
    source: str, values: set[str], takers: dict[str, int]
) -> list[tuple[int, str]]:
    return [
        (argument.lineno, argument.value)
        for call in ast.walk(ast.parse(source))
        if isinstance(call, ast.Call) and callee_name(call) in takers
        for argument in kind_arguments(call, takers[callee_name(call) or ""])
        if isinstance(argument, ast.Constant) and argument.value in values
    ]


def is_store_owned(name: str) -> bool:
    path = Path(name)
    return path.is_relative_to(OWNER) or path.is_relative_to(CONTRACT_SUITE)


def main(paths: list[str]) -> int:
    modules = store_sources()
    values = kind_values(modules)
    takers = takes_a_kind(modules)
    if not values:
        print(
            f"No Kind enum found under {OWNER}: has the Store moved?", file=sys.stderr
        )
        return 1
    failures = [
        f'{name}:{line}: "{value}"'
        for name in map(os.path.relpath, paths)
        if not is_store_owned(name)
        for line, value in literal_kinds(Path(name).read_text(), values, takers)
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
