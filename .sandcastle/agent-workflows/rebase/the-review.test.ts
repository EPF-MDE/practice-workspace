import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { answersMergeable, type Mergeable } from "../shared/fake-gh-mergeable";
import { stepScript } from "../shared/step-script";

const decideWhetherTheReviewStands = stepScript(
  "agent-rebase.yml",
  "rebase",
  "Decide whether the review stands"
);

const handItToTheReview = stepScript(
  "agent-rebase.yml",
  "rebase",
  "Hand it to the review"
);

const OLD_HEAD = "a".repeat(40);
const NEW_HEAD = "b".repeat(40);

const outputOf = (file: string, name: string) =>
  readFileSync(file, "utf8")
    .split("\n")
    .find((line) => line.startsWith(`${name}=`))
    ?.slice(`${name}=`.length);

type Rebase = {
  outcome: "up-to-date" | "rebased" | "conflicts";
  diff?: "unchanged" | "changed";
  byAgent?: boolean;
  reviewWaiting?: boolean;
};

const decide = ({
  outcome,
  diff,
  byAgent = false,
  reviewWaiting = false,
}: Rebase) => {
  const output = join(mkdtempSync(join(tmpdir(), "review-decide-")), "output");
  writeFileSync(output, "");
  const result = spawnSync("bash", ["-c", decideWhetherTheReviewStands], {
    encoding: "utf8",
    env: {
      ...process.env,
      GITHUB_OUTPUT: output,
      OUTCOME: outcome,
      DIFF: diff ?? "",
      BY_AGENT: byAgent ? "true" : "",
      WAITING: reviewWaiting ? "true" : "false",
    },
  });
  return { status: result.status, review: outputOf(output, "review") };
};

describe("whether a rebase keeps the review", () => {
  it.each<[string, Rebase]>([
    ["already on top of its base", { outcome: "up-to-date" }],
    [
      "rebased by the script, its diff unchanged",
      { outcome: "rebased", diff: "unchanged" },
    ],
  ])("keeps it for a pull request %s", (_, rebase) => {
    expect(decide(rebase)).toEqual({ status: 0, review: "keep" });
  });

  it.each<[string, Rebase]>([
    [
      "rebased by the script, its diff changed",
      { outcome: "rebased", diff: "changed" },
    ],
    [
      "whose conflicts an agent resolved",
      { outcome: "conflicts", byAgent: true },
    ],
    [
      "whose failing check an agent fixed",
      { outcome: "rebased", diff: "unchanged", byAgent: true },
    ],
    [
      "rebased by the script, its diff unchanged, agent:review waiting",
      { outcome: "rebased", diff: "unchanged", reviewWaiting: true },
    ],
    [
      "already on top of its base, agent:review waiting",
      { outcome: "up-to-date", reviewWaiting: true },
    ],
  ])("asks for one on a pull request %s", (_, rebase) => {
    expect(decide(rebase)).toEqual({ status: 0, review: "request" });
  });
});

type PullRequest = {
  labels?: string[];
  mergeable?: Mergeable[];
  statuses?:
    | { context: string; state: string; target_url?: string }[]
    | "unreadable";
};

const writeStatuses = (
  dir: string,
  statuses: NonNullable<PullRequest["statuses"]>
) => {
  if (statuses === "unreadable") return;
  writeFileSync(
    join(dir, "status.json"),
    JSON.stringify({
      statuses: statuses.map((status) => ({ description: null, ...status })),
    })
  );
};

const fakeGh = ({
  labels = [],
  mergeable = ["MERGEABLE"],
  statuses = [],
}: PullRequest): string => {
  const dir = mkdtempSync(join(tmpdir(), "review-hand-off-"));
  writeFileSync(
    join(dir, "labels.json"),
    JSON.stringify({ labels: labels.map((name) => ({ name })) })
  );
  const mergeableCase = answersMergeable(dir, 7, mergeable);
  writeStatuses(dir, statuses);
  for (const log of ["edits", "comments", "posted"]) {
    writeFileSync(join(dir, log), "");
  }
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/bash
case "$*" in
  "pr view 7 --json labels") cat "${dir}/labels.json" ;;
${mergeableCase}
  "pr edit 7 "*) echo "$4 $5" >> "${dir}/edits" ;;
  "pr comment 7 "*) echo "comment" >> "${dir}/comments" ;;
  "api repos/EPF-MDE/practice-workspace/commits/${OLD_HEAD}/status") cat "${dir}/status.json" ;;
  "api --method POST repos/EPF-MDE/practice-workspace/statuses/${NEW_HEAD} --input "*)
    cat "$6" >> "${dir}/posted" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
`
  );
  chmodSync(join(dir, "gh"), 0o755);
  return dir;
};

type HandOff = PullRequest & {
  review: "keep" | "request";
  pushed?: boolean;
};

const handOff = ({ review, pushed = true, ...pullRequest }: HandOff) => {
  const dir = fakeGh(pullRequest);
  const result = spawnSync("bash", ["-c", handItToTheReview], {
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      GH_REPO: "EPF-MDE/practice-workspace",
      PR_NUMBER: "7",
      REVIEW: review,
      OLD_HEAD,
      NEW_HEAD: pushed ? NEW_HEAD : "",
      SETTLE_TRIES: "3",
      SETTLE_SECONDS: "0",
    },
  });
  const lines = (log: string) =>
    readFileSync(join(dir, log), "utf8").split("\n").filter(Boolean);
  return {
    status: result.status,
    stdout: result.stdout,
    stderr: result.stderr,
    edits: lines("edits"),
    comments: lines("comments").length,
    posted: lines("posted").map((line) => JSON.parse(line) as object),
    mergeableAsked: Number(readFileSync(join(dir, "asked"), "utf8")),
  };
};

describe("a rebased pull request that keeps its review", () => {
  it("keeps the review: its agent-review status goes on the new head", () => {
    const { status, stderr, edits, posted } = handOff({
      review: "keep",
      statuses: [
        { context: "check", state: "success" },
        { context: "agent-review", state: "success", target_url: "https://x" },
      ],
    });

    expect(stderr).toBe("");
    expect(status).toBe(0);
    expect(edits).toEqual([]);
    expect(posted).toEqual([
      { state: "success", context: "agent-review", target_url: "https://x" },
    ]);
  });

  it("keeps a review that never ran: nothing to carry over, no label", () => {
    const { status, edits, posted } = handOff({ review: "keep" });

    expect(status).toBe(0);
    expect(edits).toEqual([]);
    expect(posted).toEqual([]);
  });

  it("still keeps the review, and warns, when the old head's statuses cannot be read", () => {
    const { status, stdout, edits, posted } = handOff({
      review: "keep",
      statuses: "unreadable",
    });

    expect(status).toBe(0);
    expect(stdout).toContain("::warning::");
    expect(edits).toEqual([]);
    expect(posted).toEqual([]);
  });

  it("carries no status over a review still running", () => {
    const { posted } = handOff({
      review: "keep",
      statuses: [{ context: "agent-review", state: "pending" }],
    });

    expect(posted).toEqual([]);
  });
});

describe("a rebased pull request handed to the review", () => {
  it("asks for the review once GitHub calls the pull request mergeable", () => {
    const { status, edits, comments, mergeableAsked } = handOff({
      review: "request",
      mergeable: ["UNKNOWN", "MERGEABLE"],
    });

    expect(status).toBe(0);
    expect(mergeableAsked).toBe(2);
    expect(edits).toEqual(["--add-label agent:review"]);
    expect(comments).toBe(0);
  });

  it("puts back an agent:review left waiting while the pull request conflicted", () => {
    const { edits, posted } = handOff({
      review: "request",
      pushed: false,
      labels: ["agent:review"],
      mergeable: ["CONFLICTING", "MERGEABLE"],
    });

    expect(edits).toEqual([
      "--remove-label agent:review",
      "--add-label agent:review",
    ]);
    expect(posted).toEqual([]);
  });

  it("still asks, and says the label may start nothing, when GitHub never calls it mergeable", () => {
    const { status, edits, comments, mergeableAsked } = handOff({
      review: "request",
      mergeable: ["UNKNOWN"],
    });

    expect(status).toBe(0);
    expect(mergeableAsked).toBe(3);
    expect(edits).toEqual(["--add-label agent:review"]);
    expect(comments).toBe(1);
  });
});
