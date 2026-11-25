import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-workflow-triggers.js");

const checkWorkflow = (on) => {
  const file = join(
    mkdtempSync(join(tmpdir(), "check-workflow-triggers-")),
    "agent.yml"
  );
  writeFileSync(
    file,
    `# pull_request_target: a comment may name it.
${on}
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo "workflow_run is only a word here"
`
  );
  return spawnSync("node", [script, file], { encoding: "utf8" });
};

describe("check-workflow-triggers", () => {
  it("passes pull_request and issues", () => {
    const result = checkWorkflow(`on:
  pull_request:
  issues:
    types: [labeled]`);

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses a pull_request_target job that does not skip a fork's pull request", () => {
    const result = checkWorkflow(`on:
  pull_request_target:
    types: [labeled]`);

    expect(result.stderr).toContain(
      "agent.yml: pull_request_target, job build does not skip a fork's pull request"
    );
    expect(result.status).toBe(1);
  });

  it("refuses workflow_run", () => {
    const result = checkWorkflow(`on:
  workflow_run:
    workflows: [Check]`);

    expect(result.stderr).toContain("agent.yml: workflow_run");
    expect(result.status).toBe(1);
  });

  it("refuses a trigger given as a string", () => {
    const result = checkWorkflow("on: workflow_run");

    expect(result.stderr).toContain("agent.yml: workflow_run");
    expect(result.status).toBe(1);
  });

  it("refuses a trigger given in a list", () => {
    const result = checkWorkflow("on: [push, workflow_run]");

    expect(result.stderr).toContain("agent.yml: workflow_run");
    expect(result.status).toBe(1);
  });
});

const SAME_REPOSITORY =
  "github.event.pull_request.head.repo.full_name == github.repository";

const checkLabelWorkflow = (steps) => {
  const file = join(
    mkdtempSync(join(tmpdir(), "check-workflow-triggers-")),
    "labels.yml"
  );
  writeFileSync(
    file,
    `on:
  pull_request_target:
    types: [labeled]
jobs:
  answer:
    if: github.event.label.name == 'agent:review' && ${SAME_REPOSITORY}
    runs-on: ubuntu-latest
    env:
      PR_NUMBER: \${{ github.event.pull_request.number }}
    steps:
${steps}
`
  );
  return spawnSync("node", [script, file], { encoding: "utf8" });
};

describe("check-workflow-triggers, on pull_request_target", () => {
  it("passes a job that skips forks and runs only gh", () => {
    const result = checkLabelWorkflow(`      - name: Answer
        run: gh pr comment "$PR_NUMBER" --body "Rebasing first."`);

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it.each([
    [
      "uses an action",
      `      - name: Checkout
        uses: actions/checkout@v7`,
    ],
    [
      "calls git",
      `      - name: Fetch
        run: git fetch origin "refs/pull/$PR_NUMBER/head"`,
    ],
    [
      "calls git",
      `      - name: Checkout
        run: gh pr checkout "$PR_NUMBER"`,
    ],
    [
      "interpolates an expression",
      `      - name: Echo
        run: echo "\${{ github.event.pull_request.title }}"`,
    ],
  ])("refuses a step that %s", (problem, steps) => {
    const result = checkLabelWorkflow(steps);

    expect(result.stderr).toContain(
      `labels.yml: pull_request_target, job answer, step`
    );
    expect(result.stderr).toContain(problem);
    expect(result.status).toBe(1);
  });
});
