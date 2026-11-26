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

const openIssuesOneToNine = Array.from({ length: 9 }, (_, i) => ({
  number: i + 1,
  id: 100 + i,
}));

const check = (batch: number[], plan: unknown) =>
  spawnSync("bash", ["-c", checkThePlan ?? "exit 99"], {
    encoding: "utf8",
    env: {
      ...process.env,
      BATCH: JSON.stringify(batch),
      OPEN: JSON.stringify(openIssuesOneToNine),
      PLAN: JSON.stringify(plan),
    },
  });

const entry = (number: number, overrides = {}) => ({
  number,
  tag: "easy-call",
  comment: `Findings for #${number}.`,
  ...overrides,
});

const decision = {
  question: "Which name does the Step take?",
  options: ["Keep the old one", "Use the new one"],
};

describe("the explore workflow's plan check", () => {
  it("accepts one entry per issue of the batch, with a duplicate on a survivor", () => {
    const result = check([3, 4, 5, 6], {
      issues: [
        entry(3),
        entry(4, { tag: "needs-a-human", decision }),
        entry(5, { duplicate_of: 3 }),
        entry(6, { tag: "blocked", blocked_by: [3] }),
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

describe("the explore workflow's plan check, on blocked and needs-a-human", () => {
  it("refuses a blocked issue that names no issue it is blocked by", () => {
    const result = check([3], { issues: [entry(3, { tag: "blocked" })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 is blocked but names no issue");
  });

  it("refuses blockers on an issue that is not blocked", () => {
    const result = check([3], { issues: [entry(3, { blocked_by: [1] })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 names blockers but is not");
  });

  it("refuses an issue blocked by itself", () => {
    const result = check([3], {
      issues: [entry(3, { tag: "blocked", blocked_by: [3] })],
    });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 is blocked by itself");
  });

  it("refuses an issue that needs a human but asks no question with options", () => {
    for (const asked of [
      {},
      { decision: { question: "Which one?", options: ["This one"] } },
      { decision: { question: " ", options: ["This", "That"] } },
    ]) {
      const result = check([3], {
        issues: [entry(3, { tag: "needs-a-human", ...asked })],
      });

      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("#3 needs a human but asks no question");
    }
  });

  it("refuses a question on an issue that does not need a human", () => {
    const result = check([3], { issues: [entry(3, { decision })] });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("#3 asks a question but does not need");
  });
});

describe("the explore workflow's plan check, on blockers", () => {
  it("refuses a blocker that is not an open issue, so nothing loops through explore", () => {
    const result = check([3], {
      issues: [entry(3, { tag: "blocked", blocked_by: [1, 42] })],
    });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "#3 is blocked by #42, which is not an open issue"
    );
    expect(result.stderr).not.toContain("#1,");
  });

  it("refuses a blocker this run closes as a duplicate", () => {
    const result = check([3, 4, 5], {
      issues: [
        entry(3),
        entry(4, { duplicate_of: 3 }),
        entry(5, { tag: "blocked", blocked_by: [4] }),
      ],
    });

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "#5 is blocked by #4, which this run closes"
    );
  });
});
