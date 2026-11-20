import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

const repository = join(import.meta.dirname, "..");
const pythonCheck = join(repository, "scripts", "check-comments.py");
const oxlint = join(repository, "node_modules", ".bin", "oxlint");

const repositoryWith = (files, baseline) => {
  const root = mkdtempSync(join(tmpdir(), "check-comments-"));
  const all = {
    ...files,
    "lint-rules/comments-baseline.json": JSON.stringify(baseline),
    ".oxlintrc.json": JSON.stringify({
      jsPlugins: [join(repository, "lint-rules", "comments.js")],
      rules: { "comments/no-comments": "error" },
    }),
  };
  for (const [file, contents] of Object.entries(all)) {
    mkdirSync(join(root, dirname(file)), { recursive: true });
    writeFileSync(join(root, file), contents);
  }
  return root;
};

const lint = (files, baseline = {}) =>
  spawnSync(oxlint, ["-c", ".oxlintrc.json", ...Object.keys(files)], {
    cwd: repositoryWith(files, baseline),
    encoding: "utf8",
  });

const checkPython = (files, baseline = {}) =>
  spawnSync("python3", [pythonCheck, ...Object.keys(files)], {
    cwd: repositoryWith(files, baseline),
    encoding: "utf8",
  });

describe("comments/no-comments, the oxlint rule", () => {
  it("refuses a comment in a file the baseline does not list", () => {
    const result = lint({ "a.ts": "// says what\nexport const a = 1;\n" });

    expect(result.stdout).toContain("1 comments, and a.ts may hold 0");
    expect(result.status).toBe(1);
  });

  it("passes a file holding as many comments as its baseline", () => {
    const result = lint(
      { "a.tsx": "/* one */\nexport const a = <b>{/* two */}</b>;\n" },
      { "a.tsx": 2 }
    );

    expect(result.status).toBe(0);
  });

  it("asks for a lower entry once a comment is gone", () => {
    const result = lint({ "a.ts": "export const a = 1;\n" }, { "a.ts": 1 });

    expect(result.stdout).toContain("lower its entry to 0");
    expect(result.status).toBe(1);
  });

  it("does not count a tool's directive", () => {
    const result = lint({
      "a.ts":
        "// @ts-expect-error a string\nexport const a: number = 'b';\n// oxlint-disable-next-line no-var\nvar b = 1;\n",
    });

    expect(result.stdout).not.toContain("no-comments");
  });
});

describe("check-comments.py, for Python and shell", () => {
  it("counts a Python docstring and a # comment", () => {
    const result = checkPython({
      "a.py": 'def f() -> None:\n    """Says what."""\n    # and how\n',
    });

    expect(result.stderr).toContain("a.py: 2 comments, and it may hold 0");
    expect(result.status).toBe(1);
  });

  it("does not count noqa, type: ignore or a shebang", () => {
    const result = checkPython({
      "a.py": "import os  # noqa: F401\nx: int = 'a'  # type: ignore\n",
      "a.sh": "#!/bin/sh\necho a\n",
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("asks for a lower entry once a comment is gone", () => {
    const result = checkPython({ "a.sh": "echo a\n" }, { "a.sh": 3 });

    expect(result.stderr).toContain("lower its entry to 0");
    expect(result.status).toBe(1);
  });

  it("refuses an entry for a file that no longer exists", () => {
    const result = checkPython({}, { "gone.py": 1 });

    expect(result.stderr).toContain("gone.py: in lint-rules");
    expect(result.status).toBe(1);
  });
});
