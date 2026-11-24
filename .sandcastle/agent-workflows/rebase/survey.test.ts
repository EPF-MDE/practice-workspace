import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { workflowStep } from "./workflow-step";

const findThePullRequests = workflowStep(
  "survey",
  "Find the pull requests to rebase"
);

type PullRequest = {
  number: number;
  mergeable?: "MERGEABLE" | "CONFLICTING" | "UNKNOWN";
  fork?: boolean;
  labels?: string[];
};

const listed = ({
  number,
  mergeable = "CONFLICTING",
  fork = false,
  labels = [],
}: PullRequest) => ({
  number,
  mergeable,
  isCrossRepository: fork,
  labels: labels.map((name) => ({ name })),
});

const survey = (
  ...lists: PullRequest[][]
): { status: number | null; stderr: string; numbers: number[] } => {
  const dir = mkdtempSync(join(tmpdir(), "rebase-survey-"));
  lists.forEach((list, index) => {
    writeFileSync(
      join(dir, `list-${index}.json`),
      JSON.stringify(list.map(listed))
    );
  });
  writeFileSync(join(dir, "calls"), "0");
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/sh
[ "$1 $2" = "pr list" ] || { echo "unexpected gh $*" >&2; exit 1; }
calls=$(cat "${dir}/calls")
echo $((calls + 1)) > "${dir}/calls"
last=${lists.length - 1}
[ "$calls" -gt "$last" ] && calls=$last
cat "${dir}/list-$calls.json"
`
  );
  chmodSync(join(dir, "gh"), 0o755);
  const output = join(dir, "output");
  writeFileSync(output, "");

  const result = spawnSync("bash", ["-c", findThePullRequests], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      GITHUB_OUTPUT: output,
      SETTLE_SECONDS: "0",
    },
  });
  const line = readFileSync(output, "utf8")
    .split("\n")
    .find((entry) => entry.startsWith("prs="));
  return {
    status: result.status,
    stderr: result.stderr,
    numbers: line ? JSON.parse(line.slice("prs=".length)) : [],
  };
};

describe("the rebase survey", () => {
  it("takes every pull request GitHub says conflicts with its base", () => {
    const { status, stderr, numbers } = survey([
      { number: 1 },
      { number: 2, mergeable: "MERGEABLE" },
      { number: 3 },
    ]);

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(numbers).toEqual([1, 3]);
  });

  it("leaves a pull request labelled agent:blocked to its human", () => {
    const { numbers } = survey([
      { number: 1, labels: ["agent:blocked"] },
      { number: 2 },
    ]);

    expect(numbers).toEqual([2]);
  });

  it("leaves a pull request an agent is working on", () => {
    const { numbers } = survey([
      { number: 1, labels: ["agent:in-progress"] },
      { number: 2 },
    ]);

    expect(numbers).toEqual([2]);
  });

  it("leaves a fork's pull request, which it cannot push to", () => {
    const { numbers } = survey([{ number: 1, fork: true }, { number: 2 }]);

    expect(numbers).toEqual([2]);
  });

  it("asks again about a pull request GitHub has not checked yet", () => {
    const { numbers } = survey(
      [{ number: 1, mergeable: "UNKNOWN" }, { number: 2 }],
      [{ number: 1 }, { number: 2 }]
    );

    expect(numbers).toEqual([1, 2]);
  });

  it("finds nothing when no pull request conflicts", () => {
    const { status, numbers } = survey([{ number: 1, mergeable: "MERGEABLE" }]);

    expect(status).toBe(0);
    expect(numbers).toEqual([]);
  });
});
