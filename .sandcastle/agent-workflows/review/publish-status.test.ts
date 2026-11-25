import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";

const publishTheStatus = stepScript(
  "agent-review.yml",
  "review",
  "Publish the verdict as the agent-review status"
);

const HEAD_SHA = "1111111111111111111111111111111111111111";

type Run = {
  push: string;
  fallback?: string;
  check: string;
  status?: { state: string; description: string };
};

const aCheckoutWithTheReviewsCommit = (): {
  dir: string;
  reviewHead: string;
} => {
  const dir = mkdtempSync(join(tmpdir(), "publish-status-"));
  execFileSync("git", ["init", "-q", dir]);
  execFileSync(
    "git",
    [
      "-c",
      "user.name=test",
      "-c",
      "user.email=test@example.com",
      "commit",
      "-q",
      "--allow-empty",
      "-m",
      "the review's fix",
    ],
    { cwd: dir }
  );
  const reviewHead = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: dir,
    encoding: "utf8",
  }).trim();
  return { dir, reviewHead };
};

const publish = ({ push, fallback = "", check, status }: Run) => {
  const { dir, reviewHead } = aCheckoutWithTheReviewsCommit();
  if (status) {
    writeFileSync(join(dir, "review-status.json"), JSON.stringify(status));
  }
  const calls = join(dir, "calls");
  writeFileSync(
    join(dir, "gh"),
    `#!/bin/sh\nprintf '%s\\n' "$@" > "${calls}"\n`
  );
  chmodSync(join(dir, "gh"), 0o755);

  const result = spawnSync("bash", ["-c", publishTheStatus], {
    cwd: dir,
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${dir}:${process.env.PATH}`,
      RUNNER_TEMP: dir,
      GH_REPO: "owner/repo",
      HEAD_SHA,
      RUN_URL: "https://example.com/run",
      PUSH: push,
      FALLBACK: fallback,
      CHECK: check,
    },
  });
  const args = readFileSync(calls, "utf8").split("\n");
  const field = (name: string) =>
    args.find((arg) => arg.startsWith(`${name}=`))?.slice(name.length + 1);
  return {
    ...result,
    reviewHead,
    endpoint: args.find((arg) => arg.startsWith("repos/")),
    state: field("state"),
    description: field("description"),
  };
};

const passing = { state: "success", description: "Both axes pass." };

describe("the agent-review status", () => {
  it("passes the review's own head when the verdict and check pass", () => {
    const { status, endpoint, state, reviewHead } = publish({
      push: "success",
      check: "success",
      status: passing,
    });

    expect(status).toBe(0);
    expect(endpoint).toBe(`repos/owner/repo/statuses/${reviewHead}`);
    expect(state).toBe("success");
  });

  it("fails with the verdict's reason when the verdict fails", () => {
    const { state, description } = publish({
      push: "success",
      check: "success",
      status: { state: "failure", description: "The review left 1 finding." },
    });

    expect([state, description]).toEqual([
      "failure",
      "The review left 1 finding.",
    ]);
  });

  it("fails a passing verdict when check failed after it", () => {
    const { state } = publish({
      push: "success",
      check: "failure",
      status: passing,
    });

    expect(state).toBe("failure");
  });

  it("fails the head it read when the push went to another branch", () => {
    const { endpoint, state } = publish({
      push: "success",
      fallback: "true",
      check: "success",
      status: passing,
    });

    expect(endpoint).toBe(`repos/owner/repo/statuses/${HEAD_SHA}`);
    expect(state).toBe("failure");
  });

  it("fails the head it read when the run broke before its verdict", () => {
    const { endpoint, state } = publish({ push: "skipped", check: "skipped" });

    expect(endpoint).toBe(`repos/owner/repo/statuses/${HEAD_SHA}`);
    expect(state).toBe("failure");
  });
});
