// The apply job's "Check the plan" step, run as the workflow runs it: its own
// script, from agent-explore.yml, with the batch and the plan in its env.

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";

type Step = { name?: string; run?: string };
type Workflow = { jobs: Record<string, { steps: Step[] }> };

const workflow = parse(
  readFileSync(
    join(import.meta.dirname, "../../../.github/workflows/agent-explore.yml"),
    "utf8"
  )
) as Workflow;

const checkThePlan = workflow.jobs.apply.steps.find(
  (step) => step.name === "Check the plan"
)?.run;

const check = (batch: number[], plan: unknown) =>
  spawnSync("bash", ["-c", checkThePlan ?? "exit 99"], {
    encoding: "utf8",
    env: {
      ...process.env,
      BATCH: JSON.stringify(batch),
      PLAN: JSON.stringify(plan),
    },
  });

const entry = (number: number, overrides = {}) => ({
  number,
  tag: "easy-call",
  comment: `Findings for #${number}.`,
  ...overrides,
});

describe("the explore workflow's plan check", () => {
  it("accepts one entry per issue of the batch, with a duplicate on a survivor", () => {
    const result = check([3, 4, 5], {
      issues: [
        entry(3),
        entry(4, { tag: "needs-a-human" }),
        entry(5, { duplicate_of: 3 }),
      ],
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses a plan that leaves an issue of the batch out", () => {
    const result = check([3, 4], { issues: [entry(3)] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("exactly one entry for each of [3,4]");
  });

  it("refuses a tag the workflow does not branch on", () => {
    const result = check([3], { issues: [entry(3, { tag: "ship-it" })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 has a tag this workflow does not know");
  });

  it("refuses an empty comment", () => {
    const result = check([3], { issues: [entry(3, { comment: "  " })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 has an empty comment");
  });

  it("refuses a duplicate of an issue that is itself a duplicate", () => {
    const result = check([3, 4, 5], {
      issues: [
        entry(3, { duplicate_of: 4 }),
        entry(4, { duplicate_of: 5 }),
        entry(5),
      ],
    });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 is a duplicate of #4");
  });

  it("refuses a duplicate of an issue outside the batch", () => {
    const result = check([3], { issues: [entry(3, { duplicate_of: 1 })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 is a duplicate of #1");
  });
});
