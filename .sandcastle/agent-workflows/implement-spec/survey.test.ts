import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const findTheFrontier = stepScript(
  "agent-implement-spec.yml",
  "survey",
  "Find the spec and the frontier ticket"
);

type Ticket = {
  number: number;
  state: "OPEN" | "CLOSED";
  position: number;
  blockedBy?: number[];
  labels?: string[];
  body?: string;
};

const SPEC = 40;

const issue =
  (queue: Ticket[]) =>
  ({
    number,
    state,
    position,
    blockedBy = [],
    labels = [],
    body = "",
  }: Ticket) => ({
    number,
    state,
    labels: [`spec:${SPEC}`, ...labels].map((name) => ({ name })),
    body: `Part of #${SPEC}\n\nPosition: ${position}\n${body}Shape: service-module\n\n---\n\nThe ticket.`,
    blockedBy: {
      nodes: blockedBy.map((blocker) => ({
        number: blocker,
        state: queue.find((ticket) => ticket.number === blocker)?.state,
      })),
      totalCount: blockedBy.length,
    },
  });

const pullRequest = (ticket: number) => ({
  number: 100 + ticket,
  headRefName: `agent/spec-${SPEC}-ticket-${ticket}-123456`,
});

const survey = (queue: Ticket[], openPullRequests: number[] = []) => {
  const dir = mkdtempSync(join(tmpdir(), "survey-"));
  writeFileSync(
    join(dir, "issues.json"),
    JSON.stringify(queue.map(issue(queue)))
  );
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

  const result = spawnSync("bash", ["-c", findTheFrontier], {
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
  blockedBy: number[] = [],
  labels = ["agent:queued"]
): Ticket => ({
  number,
  state: "OPEN",
  position: number,
  blockedBy,
  labels,
});

const closed = (number: number, blockedBy: number[] = []): Ticket => ({
  number,
  state: "CLOSED",
  position: number,
  blockedBy,
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

describe("the implement-spec survey's blockers", () => {
  it("reads no `Depends on:` line, only the ticket's blocked-by relations", () => {
    const { outputs } = survey([
      open(1, [], ["agent:blocked"]),
      { ...open(2), body: "Depends on: 1\n" },
    ]);

    expect(outputs).toMatchObject({ mode: "implement", ticket: "2" });
  });

  it("builds nothing whose blocker is open, even out of position order", () => {
    const { outputs } = survey([open(1, [3]), open(2, [3], []), open(3)]);

    expect(outputs).toMatchObject({ mode: "implement", ticket: "3" });
  });

  it("names, when the chain stops, each waiting ticket and its open blockers", () => {
    const { stdout, outputs } = survey(
      [closed(1), open(2, [1], []), open(3, [1, 2]), open(4, [3])],
      [2]
    );

    expect(outputs.mode).toBe("waiting");
    expect(stdout).toContain("#2 waits on its pull request #102");
    expect(stdout).toContain("#3 waits on #2 (pull request #102)");
    expect(stdout).toContain("#4 waits on #3");
  });

  it("names a parked blocker as parked", () => {
    const { stdout, outputs } = survey([
      open(1, [], ["agent:blocked"]),
      open(2, [1]),
    ]);

    expect(outputs.mode).toBe("drained");
    expect(stdout).toContain("#2 waits on #1 (parked)");
  });

  it("does not wait on the pull request of a ticket already closed", () => {
    const { outputs } = survey([closed(1), open(2, [3]), open(3, [2])], [1]);

    expect(outputs.mode).toBe("drained");
  });
});
