import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-store-kinds.py");

const KIND_ENUM = `from enum import StrEnum


class Kind(StrEnum):
    ANSWER = "answer"
    SELF_ASSESSMENT = "self-assessment"
`;

const checkCode = (files) => {
  const root = mkdtempSync(join(tmpdir(), "check-store-kinds-"));
  const all = { "backend/app/store/_internal/model.py": KIND_ENUM, ...files };
  for (const [file, contents] of Object.entries(all)) {
    mkdirSync(join(root, dirname(file)), { recursive: true });
    writeFileSync(join(root, file), contents);
  }
  return spawnSync("python3", [script, ...Object.keys(all)], {
    cwd: root,
    encoding: "utf8",
  });
};

describe("check-store-kinds", () => {
  it("passes a kind named through its enum, and the same word for a Step", () => {
    const result = checkCode({
      "backend/app/practice/steps.py": `from app.store import Kind


def answered(record, step):
    return step.kind == "answer" and record.latest(Kind.ANSWER, "C1", step.id)
`,
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("passes the Store's own modules and its contract suite", () => {
    const result = checkCode({
      "backend/app/store/github.py": 'kind = Kind("answer")\n',
      "backend/tests/store_contract/test_sends.py":
        'assert record.all(Kind("self-assessment")) == []\n',
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses a kind written as a literal where a Record is read", () => {
    const result = checkCode({
      "backend/app/practice/closing.py": `def latest(record):
    return record.latest("self-assessment", "C1")
`,
    });

    expect(result.stderr).toContain(
      'backend/app/practice/closing.py:2: "self-assessment"'
    );
    expect(result.status).toBe(1);
  });

  it("refuses a kind written as a literal to build a Kind or an Entry", () => {
    const result = checkCode({
      "backend/tests/test_answers.py": `kind = Kind("answer")
entry = Entry(kind="answer", competency="C1")
`,
    });

    expect(result.stderr).toContain(
      'backend/tests/test_answers.py:1: "answer"'
    );
    expect(result.stderr).toContain(
      'backend/tests/test_answers.py:2: "answer"'
    );
    expect(result.status).toBe(1);
  });
});
