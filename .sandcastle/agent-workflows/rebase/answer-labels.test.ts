import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const answerTheLabel = stepScript(
  "agent-answer-labels.yml",
  "answer",
  "Answer the label"
);

type Mergeable = "MERGEABLE" | "CONFLICTING" | "UNKNOWN";

const fakeGh = (mergeable: Mergeable[]): string => {
  const dir = mkdtempSync(join(tmpdir(), "answer-labels-"));
  mergeable.forEach((state, index) => {
    writeFileSync(
      join(dir, `mergeable-${index}.json`),
      JSON.stringify({ mergeable: state })
    );
  });
  writeFileSync(join(dir, "asked"), "0");
  writeFileSync(join(dir, "calls"), "");
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/bash
case "$*" in
  "pr view 7 --json mergeable")
    asked=$(cat "${dir}/asked")
    echo $((asked + 1)) > "${dir}/asked"
    last=${mergeable.length - 1}
    [ "$asked" -gt "$last" ] && asked=$last
    cat "${dir}/mergeable-$asked.json" ;;
  "pr comment 7 --body "*) echo "comment" >> "${dir}/calls" ;;
  "workflow run agent-rebase.yml -f pr=7") echo "rebase" >> "${dir}/calls" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
`
  );
  chmodSync(join(dir, "gh"), 0o755);
  return dir;
};

const label = (name: string, ...mergeable: Mergeable[]) => {
  const dir = fakeGh(mergeable.length > 0 ? mergeable : ["MERGEABLE"]);
  const result = spawnSync("bash", ["-c", answerTheLabel], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      PR_NUMBER: "7",
      LABEL: name,
      SETTLE_TRIES: "3",
      SETTLE_SECONDS: "0",
    },
  });
  return {
    status: result.status,
    stderr: result.stderr,
    calls: readFileSync(join(dir, "calls"), "utf8").split("\n").filter(Boolean),
    asked: Number(readFileSync(join(dir, "asked"), "utf8")),
  };
};

describe("agent:rebase on a pull request", () => {
  it.each<Mergeable>(["MERGEABLE", "CONFLICTING"])(
    "starts the rebase at once on one GitHub calls %s, with no comment",
    (mergeable) => {
      const { status, stderr, calls } = label("agent:rebase", mergeable);

      expect(stderr).toBe("");
      expect(status).toBe(0);
      expect(calls).toEqual(["rebase"]);
    }
  );
});

describe("agent:review on a pull request", () => {
  it("is left to agent-review.yml when the pull request does not conflict", () => {
    const { status, calls } = label("agent:review", "MERGEABLE");

    expect(status).toBe(0);
    expect(calls).toEqual([]);
  });

  it("says the pull request conflicts, then has it rebased", () => {
    const { status, calls } = label("agent:review", "CONFLICTING");

    expect(status).toBe(0);
    expect(calls).toEqual(["comment", "rebase"]);
  });

  it("asks again while GitHub has not checked the pull request yet", () => {
    const { calls, asked } = label(
      "agent:review",
      "UNKNOWN",
      "UNKNOWN",
      "MERGEABLE"
    );

    expect(asked).toBe(3);
    expect(calls).toEqual([]);
  });

  it("has it rebased, and says so, when GitHub never says whether it conflicts", () => {
    const { status, calls, asked } = label("agent:review", "UNKNOWN");

    expect(status).toBe(0);
    expect(asked).toBe(3);
    expect(calls).toEqual(["comment", "rebase"]);
  });
});
