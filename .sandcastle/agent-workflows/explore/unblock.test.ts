import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const sendBack = stepScript(
  "agent-explore.yml",
  "unblock",
  "Send the issues it blocked back to explore"
);

type Issue = { number: number; state: "open" | "closed"; labels?: string[] };

const issue = ({ number, state, labels = [] }: Issue) => ({
  number,
  state,
  labels: labels.map((name) => ({ name })),
});

type Relations = { blocking: Issue[]; blockedBy: Record<number, Issue[]> };

const close = (closed: number, { blocking, blockedBy }: Relations) => {
  const dir = mkdtempSync(join(tmpdir(), "unblock-"));
  writeFileSync(join(dir, "calls"), "");
  const answer = (endpoint: string, issues: Issue[]) => {
    const file = join(dir, `${endpoint.replaceAll("/", "-")}.json`);
    writeFileSync(file, JSON.stringify(issues.map(issue)));
    return `  "api --paginate repos/R/issues/${endpoint} --jq "*) jq -r "$5" "${file}" ;;`;
  };
  const lists = [
    answer(`${closed}/dependencies/blocking`, blocking),
    ...Object.entries(blockedBy).map(([n, issues]) =>
      answer(`${n}/dependencies/blocked_by`, issues)
    ),
  ];
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/bash
case "$*" in
${lists.join("\n")}
  "issue edit "*|"issue comment "*) echo "$*" >> "${dir}/calls" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
`
  );
  chmodSync(join(dir, "gh"), 0o755);
  const result = spawnSync("bash", ["-c", sendBack], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      GH_REPO: "R",
      CLOSED: String(closed),
    },
  });
  return {
    status: result.status,
    stderr: result.stderr,
    calls: readFileSync(join(dir, "calls"), "utf8").split("\n").filter(Boolean),
  };
};

const blocked = (number: number): Issue => ({
  number,
  state: "open",
  labels: ["agent:blocked-by-ticket"],
});

describe("closing an issue that blocks others", () => {
  it("sends back to explore an issue whose last blocker it was", () => {
    const { status, stderr, calls } = close(3, {
      blocking: [blocked(7)],
      blockedBy: {
        7: [
          { number: 3, state: "closed" },
          { number: 4, state: "closed" },
        ],
      },
    });

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(calls).toHaveLength(2);
    expect(calls[0]).toBe(
      "issue edit 7 --remove-label agent:blocked-by-ticket --add-label agent:explore"
    );
    expect(calls[1]).toMatch(/^issue comment 7 .*<!-- factory:status -->$/);
  });

  it("leaves an issue that another open issue still blocks", () => {
    const { status, calls } = close(3, {
      blocking: [blocked(7)],
      blockedBy: {
        7: [
          { number: 3, state: "closed" },
          { number: 4, state: "open" },
        ],
      },
    });

    expect(status).toBe(0);
    expect(calls).toEqual([]);
  });

  it("leaves an issue the factory does not hold as blocked, or one closed", () => {
    const { status, calls } = close(3, {
      blocking: [
        { number: 7, state: "open", labels: ["needs-a-human"] },
        { number: 8, state: "closed", labels: ["agent:blocked-by-ticket"] },
      ],
      blockedBy: {},
    });

    expect(status).toBe(0);
    expect(calls).toEqual([]);
  });
});
