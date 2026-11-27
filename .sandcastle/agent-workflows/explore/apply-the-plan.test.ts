import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const applyThePlan = stepScript("agent-explore.yml", "apply", "Apply the plan");

type Blocker = { number: number; state: "open" | "closed" };

const fakeGh = (dir: string) => `#!/bin/bash
echo "$*" >> "${dir}/calls"
case "$*" in
  "label create "*) ;;
  "issue comment "*) cp "$5" "${dir}/comment-$3.md" ;;
  "issue edit "*) ;;
  "api --paginate repos/R/issues/"*"/dependencies/blocked_by --jq "*)
    jq -r "$5" "${dir}/drawn.json" ;;
  "api --method POST repos/R/issues/"*"/dependencies/blocked_by -F issue_id="*)
    jq --argjson id "\${6#issue_id=}" --slurpfile s "${dir}/states.json" \\
      '. + [$s[0][] | select(.id == $id) | {number, state}]' "${dir}/drawn.json" > "${dir}/drawn.next"
    mv "${dir}/drawn.next" "${dir}/drawn.json" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
`;

const apply = (
  issues: unknown[],
  blockers: Blocker[],
  drawn: Blocker[] = []
) => {
  const dir = mkdtempSync(join(tmpdir(), "apply-"));
  writeFileSync(join(dir, "calls"), "");
  writeFileSync(join(dir, "drawn.json"), JSON.stringify(drawn));
  const withIds = blockers.map((b) => ({ ...b, id: 1000 + b.number }));
  writeFileSync(join(dir, "states.json"), JSON.stringify(withIds));
  writeFileSync(join(dir, "gh"), fakeGh(dir));
  chmodSync(join(dir, "gh"), 0o755);
  const script = applyThePlan.replaceAll("/tmp/", `${dir}/`);
  writeFileSync(join(dir, "plan.json"), JSON.stringify({ issues }));
  const result = spawnSync("bash", ["-c", script], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      GH_REPO: "R",
      RUN_URL: "https://run",
      OPEN: JSON.stringify(withIds),
    },
  });
  const calls = readFileSync(join(dir, "calls"), "utf8").split("\n");
  const comment = (n: number) =>
    readFileSync(join(dir, `comment-${n}.md`), "utf8");
  return { result, calls, comment };
};

const blocked = (blocked_by: number[]) => ({
  number: 7,
  tag: "blocked",
  blocked_by,
  comment: "Findings.",
});

describe("applying a plan to an issue that waits on a ticket", () => {
  it("draws each blocker by its id, once, and labels the issue blocked", () => {
    const { result, calls } = apply(
      [blocked([3, 4])],
      [
        { number: 3, state: "open" },
        { number: 4, state: "open" },
      ],
      [{ number: 3, state: "open" }]
    );

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
    const drawn = calls.filter((call) => call.includes("--method POST"));
    expect(drawn).toEqual([
      "api --method POST repos/R/issues/7/dependencies/blocked_by -F issue_id=1004 --silent",
    ]);
    expect(calls).toContain(
      "issue edit 7 --remove-label agent:in-progress --add-label agent:blocked-by-ticket"
    );
  });

  it("sends it back to explore when its blockers closed while it was explored", () => {
    const { result, calls } = apply(
      [blocked([3])],
      [{ number: 3, state: "closed" }]
    );

    expect(result.status).toBe(0);
    const labels = calls.filter((call) => call.startsWith("issue edit 7 "));
    expect(labels.at(-1)).toBe(
      "issue edit 7 --remove-label agent:blocked-by-ticket --add-label agent:explore"
    );
  });

  it("labels it blocked before it reads whether a blocker is still open", () => {
    const { calls } = apply([blocked([3])], [{ number: 3, state: "open" }]);

    const labelled = calls.indexOf(
      "issue edit 7 --remove-label agent:in-progress --add-label agent:blocked-by-ticket"
    );
    const lastRead = calls.lastIndexOf(
      'api --paginate repos/R/issues/7/dependencies/blocked_by --jq .[] | select(.state == "open") | .number'
    );
    expect(labelled).toBeGreaterThanOrEqual(0);
    expect(labelled).toBeLessThan(lastRead);
  });
});

describe("applying a plan to an issue that needs a human", () => {
  it("ends the findings with the decision and its options", () => {
    const { result, calls, comment } = apply(
      [
        {
          number: 7,
          tag: "needs-a-human",
          comment: "Findings.",
          decision: { question: "Which one?", options: ["This", "That"] },
        },
      ],
      []
    );

    expect(result.status).toBe(0);
    const body = comment(7).split("\n---\n")[0];
    expect(body.trimEnd()).toMatch(/Which one\?\s+- This\s+- That$/);
    expect(calls).toContain(
      "issue edit 7 --remove-label agent:in-progress --add-label needs-a-human"
    );
  });
});
