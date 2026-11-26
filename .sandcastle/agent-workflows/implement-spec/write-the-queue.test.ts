import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const writeTheQueue = stepScript(
  "agent-implement-spec.yml",
  "decompose",
  "Write the queue as issues"
);

const SPEC = 40;
const FIRST_ISSUE = 50;

type Ticket = { position: number; depends_on: number[] };

const fakeGh = (dir: string): void => {
  writeFileSync(join(dir, "created"), "");
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/bash
case "$1 $2" in
  "label create"|"issue comment") ;;
  "issue create")
    shift 2
    number=$(( ${FIRST_ISSUE} + $(wc -l < "${dir}/created") ))
    jq -cn --argjson number "$number" --rawfile body "${dir}/ticket-body.md" \\
      '{ number: $number, body: $body, args: $ARGS.positional }' --args -- "$@" >> "${dir}/created"
    echo "https://github.com/owner/repo/issues/$number" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
`
  );
  chmodSync(join(dir, "gh"), 0o755);
};

const writeQueue = (tickets: Ticket[]) => {
  const dir = mkdtempSync(join(tmpdir(), "write-the-queue-"));
  fakeGh(dir);
  writeFileSync(
    join(dir, "queue.json"),
    JSON.stringify({
      tickets: tickets.map((ticket) => ({
        ...ticket,
        title: `Ticket ${ticket.position}`,
        body: "## What\n\nThe ticket.",
        shape: "service-module",
      })),
    })
  );
  const result = spawnSync("bash", ["-c", writeTheQueue], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      RUNNER_TEMP: dir,
      SPEC: String(SPEC),
    },
  });
  const created = readFileSync(join(dir, "created"), "utf8")
    .split("\n")
    .filter(Boolean)
    .map(
      (line) =>
        JSON.parse(line) as { number: number; body: string; args: string[] }
    );
  const flag = (args: string[], name: string) => {
    const at = args.indexOf(name);
    return at === -1 ? undefined : args[at + 1];
  };
  return {
    ...result,
    created: created.map(({ number, body, args }) => ({
      number,
      body,
      parent: flag(args, "--parent"),
      blockedBy: flag(args, "--blocked-by"),
    })),
  };
};

describe("the implement-spec decompose loop's queue", () => {
  it("makes each ticket a sub-issue of the spec, blocked by the tickets it depends on", () => {
    const { status, stderr, created } = writeQueue([
      { position: 1, depends_on: [] },
      { position: 2, depends_on: [1] },
      { position: 3, depends_on: [1, 2] },
    ]);

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(
      created.map(({ parent, blockedBy }) => ({ parent, blockedBy }))
    ).toEqual([
      { parent: String(SPEC), blockedBy: undefined },
      { parent: String(SPEC), blockedBy: "50" },
      { parent: String(SPEC), blockedBy: "50,51" },
    ]);
  });

  it("creates the tickets in position order, whatever order the queue lists them in", () => {
    const { status, created } = writeQueue([
      { position: 2, depends_on: [1] },
      { position: 1, depends_on: [] },
    ]);

    expect(status).toBe(0);
    expect(
      created.map(({ body }) => body.match(/Position: (\d+)/)?.[1])
    ).toEqual(["1", "2"]);
    expect(created[1]?.blockedBy).toBe("50");
  });

  it("writes no `Depends on:` line in a ticket's body", () => {
    const { created } = writeQueue([
      { position: 1, depends_on: [] },
      { position: 2, depends_on: [1] },
    ]);

    expect(created.map(({ body }) => body.includes("Depends on:"))).toEqual([
      false,
      false,
    ]);
  });

  it("stops, creating nothing more, at a ticket that depends on a later position", () => {
    const { status, created } = writeQueue([
      { position: 1, depends_on: [2] },
      { position: 2, depends_on: [] },
    ]);

    expect(status).not.toBe(0);
    expect(created).toEqual([]);
  });
});
