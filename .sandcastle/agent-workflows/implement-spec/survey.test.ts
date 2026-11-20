import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";

type Step = { name?: string; run?: string };
type Workflow = { jobs: Record<string, { steps: Step[] }> };

const workflow = parse(
  readFileSync(
    join(
      import.meta.dirname,
      "../../../.github/workflows/agent-implement-spec.yml"
    ),
    "utf8"
  )
) as Workflow;

const findTheFrontier = workflow.jobs.survey.steps.find(
  (step) => step.name === "Find the spec and the frontier ticket"
)?.run;

type Ticket = {
  number: number;
  state: "OPEN" | "CLOSED";
  position: number;
  depends?: number[];
  labels?: string[];
};

const SPEC = 40;

const issue = ({
  number,
  state,
  position,
  depends = [],
  labels = [],
}: Ticket) => ({
  number,
  title: `Ticket ${number}`,
  state,
  labels: [`spec:${SPEC}`, ...labels].map((name) => ({ name })),
  body: `Part of #${SPEC}\n\nPosition: ${position}\nDepends on: ${depends.join(", ")}\nShape: service-module\n\n---\n\nThe ticket.`,
});

const pullRequest = (ticket: number) => ({
  number: 100 + ticket,
  headRefName: `agent/spec-${SPEC}-ticket-${ticket}-123456`,
});

const survey = (queue: Ticket[], openPullRequests: number[] = []) => {
  const dir = mkdtempSync(join(tmpdir(), "survey-"));
  writeFileSync(join(dir, "issues.json"), JSON.stringify(queue.map(issue)));
  writeFileSync(
    join(dir, "pulls.json"),
    JSON.stringify(openPullRequests.map(pullRequest))
  );
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/sh\ncase "$1 $2" in\n  "issue list") cat "${dir}/issues.json" ;;\n  "pr list") cat "${dir}/pulls.json" ;;\n  *) echo "unexpected gh $*" >&2; exit 1 ;;\nesac\n`
  );
  chmodSync(join(dir, "gh"), 0o755);
  const output = join(dir, "output");
  writeFileSync(output, "");

  const result = spawnSync("bash", ["-c", findTheFrontier ?? "exit 99"], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      REQUESTED_SPEC: String(SPEC),
      GITHUB_OUTPUT: output,
    },
  });
  const outputs = Object.fromEntries(
    readFileSync(output, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((line) => line.split("=", 2))
  );
  return { ...result, outputs };
};

const open = (
  number: number,
  depends: number[] = [],
  labels = ["agent:queued"]
): Ticket => ({
  number,
  state: "OPEN",
  position: number,
  depends,
  labels,
});

const closed = (number: number, depends: number[] = []): Ticket => ({
  number,
  state: "CLOSED",
  position: number,
  depends,
});

describe("the implement-spec survey's merge gate", () => {
  it("builds nothing while the dependency's pull request is open", () => {
    const { status, outputs } = survey([open(1, [], []), open(2, [1])], [1]);

    expect(status).toBe(0);
    expect(outputs.mode).toBe("waiting");
    expect(outputs.ticket).toBeUndefined();
  });

  it("builds the dependant once the dependency's pull request has merged", () => {
    const { outputs } = survey([closed(1), open(2, [1])]);

    expect(outputs).toMatchObject({ mode: "implement", ticket: "2" });
  });

  it("builds an independent ticket while another one's pull request is open", () => {
    const { outputs } = survey([open(1, [], []), open(2, [1]), open(3)], [1]);

    expect(outputs).toMatchObject({ mode: "implement", ticket: "3" });
  });
});

describe("the implement-spec survey's queue", () => {
  it("builds the first ticket of a fresh queue", () => {
    const { status, stderr, outputs } = survey([open(1), open(2, [1])]);

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(outputs).toMatchObject({ mode: "implement", ticket: "1" });
  });

  it("skips a ticket parked with agent:blocked", () => {
    const { outputs } = survey([open(1, [], ["agent:blocked"]), open(2)]);

    expect(outputs).toMatchObject({ mode: "implement", ticket: "2" });
  });

  it("reports a queue whose tickets are all closed as drained", () => {
    const { outputs } = survey([closed(1), closed(2, [1])]);

    expect(outputs.mode).toBe("drained");
  });
});
