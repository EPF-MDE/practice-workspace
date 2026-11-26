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

const close = (closed: number, relations: Record<number, Issue[]>) => {
  const dir = mkdtempSync(join(tmpdir(), "unblock-"));
  writeFileSync(join(dir, "calls"), "");
  const lists = Object.entries(relations).map(([n, issues]) => {
    const file = join(dir, `${n}.json`);
    writeFileSync(file, JSON.stringify(issues.map(issue)));
    return `  "api --paginate repos/R/issues/${n}/dependencies/"*) jq -r "$5" "${file}" ;;`;
  });
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/bash
case "$*" in
${lists.join("\n")}
  "api --paginate repos/R/issues/"*) echo "[]" | jq -r "$5" ;;
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
      3: [blocked(7)],
      7: [
        { number: 3, state: "closed" },
        { number: 4, state: "closed" },
      ],
    });

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(calls).toEqual([
      "issue edit 7 --remove-label agent:blocked-by-ticket --add-label agent:explore",
      "issue comment 7 --body Its last blocker, #3, is closed: back to explore. <!-- factory:status -->",
    ]);
  });

  it("leaves an issue that another open issue still blocks", () => {
    const { status, calls } = close(3, {
      3: [blocked(7)],
      7: [
        { number: 3, state: "closed" },
        { number: 4, state: "open" },
      ],
    });

    expect(status).toBe(0);
    expect(calls).toEqual([]);
  });

  it("leaves an issue the factory does not hold as blocked, or one closed", () => {
    const { status, calls } = close(3, {
      3: [
        { number: 7, state: "open", labels: ["needs-a-human"] },
        { number: 8, state: "closed", labels: ["agent:blocked-by-ticket"] },
      ],
    });

    expect(status).toBe(0);
    expect(calls).toEqual([]);
  });
});
