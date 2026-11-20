import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-retired-names.js");

const checkFiles = (files) => {
  const root = mkdtempSync(join(tmpdir(), "check-retired-names-"));
  for (const [file, contents] of Object.entries(files)) {
    mkdirSync(join(root, dirname(file)), { recursive: true });
    writeFileSync(join(root, file), contents);
  }
  return spawnSync("node", [script, ...Object.keys(files)], {
    cwd: root,
    encoding: "utf8",
  });
};

describe("check-retired-names", () => {
  it("passes the glossary's names, and the glossary's Avoid list", () => {
    const result = checkFiles({
      "GLOSSARY.md": "**Evidence Plan**: ... _Avoid_: Practice Plan\n",
      "backend/app/closing.py": "def evidence_plan(): ...\n",
      "frontend/src/EvidencePanel.tsx": "export const EvidencePanel = 1;\n",
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses Practice Plan in code, however it is spelt", () => {
    const result = checkFiles({
      "backend/app/closing.py": "def practice_plan(): ...\n",
      "frontend/src/Plan.tsx": "export const PracticePlan = 1;\n",
    });

    expect(result.stderr).toContain(
      "backend/app/closing.py:1: Practice Plan, now Evidence Plan"
    );
    expect(result.stderr).toContain(
      "frontend/src/Plan.tsx:1: Practice Plan, now Evidence Plan"
    );
    expect(result.status).toBe(1);
  });

  it("refuses fork reading in a test", () => {
    const result = checkFiles({
      "backend/tests/test_reading.py": "\ndef test_fork_reading(): ...\n",
    });

    expect(result.stderr).toContain(
      "backend/tests/test_reading.py:2: fork reading, now Repository reading"
    );
    expect(result.status).toBe(1);
  });

  it("refuses fork panel in the Demo course's content", () => {
    const result = checkFiles({
      "demo-course/c1.md": "Open the fork panel beside your Path.\n",
    });

    expect(result.stderr).toContain(
      "demo-course/c1.md:1: fork panel, now Evidence panel"
    );
    expect(result.status).toBe(1);
  });
});
