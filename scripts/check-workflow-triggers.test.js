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

  it("refuses pull_request_target", () => {
    const result = checkWorkflow(`on:
  pull_request_target:
    types: [labeled]`);

    expect(result.stderr).toContain("agent.yml: pull_request_target");
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
    const result = checkWorkflow("on: pull_request_target");

    expect(result.stderr).toContain("agent.yml: pull_request_target");
    expect(result.status).toBe(1);
  });

  it("refuses a trigger given in a list", () => {
    const result = checkWorkflow("on: [push, workflow_run]");

    expect(result.stderr).toContain("agent.yml: workflow_run");
    expect(result.status).toBe(1);
  });
});
