import ast
import os
import sys
from pathlib import Path

STORE = "app.store"
CONTRACT_SUITE = Path("backend/tests/store_contract")
THE_STORE_ITSELF = {
    "Store",
    "InMemoryStore",
    "GitHubStore",
    "StoreUnavailable",
    "SendTooLarge",
    "MAX_SEND_CHARS",
}


def is_store(module: str) -> bool:
    return module == STORE or module.startswith(f"{STORE}.")


def is_internal(module: str) -> bool:
    return any(part.startswith("_") for part in module.split("."))


def refused_imports(source: str) -> list[tuple[int, str]]:
    refused = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module == "app":
                refused += [
                    (node.lineno, f"app.{a.name}")
                    for a in node.names
                    if a.name == "store"
                ]
            elif is_store(node.module):
                refused += [
                    (node.lineno, f"{node.module}.{a.name}")
                    for a in node.names
                    if is_internal(node.module) or a.name not in THE_STORE_ITSELF
                ]
        elif isinstance(node, ast.Import):
            refused += [(node.lineno, a.name) for a in node.names if is_store(a.name)]
    return refused


def main(paths: list[str]) -> int:
    failures = [
        f"{name}:{line}: imports {what}"
        for name in map(os.path.relpath, paths)
        if not Path(name).is_relative_to(CONTRACT_SUITE)
        for line, what in refused_imports(Path(name).read_text())
    ]
    if failures:
        print("These tests import the Store's stored format:\n", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(
            "\nA test outside backend/tests/store_contract/ imports only the Store"
            f" itself ({', '.join(sorted(THE_STORE_ITSELF))}), and reads a Student's"
            " record back through the HTTP API.",
            file=sys.stderr,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
