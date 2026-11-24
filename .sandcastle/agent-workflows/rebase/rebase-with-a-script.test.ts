import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { workflowStep } from "./workflow-step";

const rebaseWithAScript = workflowStep("rebase", "Rebase with a script");

const IDENTITY = {
  GIT_AUTHOR_NAME: "test",
  GIT_AUTHOR_EMAIL: "test@example.com",
  GIT_COMMITTER_NAME: "test",
  GIT_COMMITTER_EMAIL: "test@example.com",
};

const inRepository = (dir: string) => ({
  git: (...args: string[]) =>
    execFileSync("git", args, {
      cwd: dir,
      encoding: "utf8",
      env: { ...process.env, ...IDENTITY },
    }).trim(),
  commit: (file: string, text: string) => {
    writeFileSync(join(dir, file), text);
    execFileSync("git", ["add", file], { cwd: dir });
    execFileSync("git", ["commit", "-qm", `${file}: ${text}`], {
      cwd: dir,
      env: { ...process.env, ...IDENTITY },
    });
  },
});

type Story = {
  onTheBranch: [file: string, text: string][];
  onMainSince: [file: string, text: string][];
};

const rebase = ({ onTheBranch, onMainSince }: Story) => {
  const dir = mkdtempSync(join(tmpdir(), "rebase-"));
  const origin = join(dir, "origin.git");
  const checkout = join(dir, "checkout");
  execFileSync("git", ["init", "-q", "--bare", "-b", "main", origin]);
  execFileSync("git", ["clone", "-q", origin, checkout]);
  const { git, commit } = inRepository(checkout);
  git("checkout", "-qb", "main");
  commit("README.md", "the start");
  git("push", "-q", "origin", "main");

  git("checkout", "-qb", "feature");
  for (const [file, text] of onTheBranch) commit(file, text);
  git("push", "-q", "origin", "feature");
  const headSha = git("rev-parse", "HEAD");

  git("checkout", "-q", "main");
  for (const [file, text] of onMainSince) commit(file, text);
  git("push", "-q", "origin", "main");
  git("checkout", "-q", "--detach", headSha);
  git("fetch", "-q", "origin");

  const output = join(dir, "output");
  writeFileSync(output, "");
  const result = spawnSync("bash", ["-c", rebaseWithAScript], {
    cwd: checkout,
    encoding: "utf8",
    env: {
      ...process.env,
      ...IDENTITY,
      GITHUB_OUTPUT: output,
      BRANCH: "feature",
      HEAD_SHA: headSha,
      BASE_REF: "main",
    },
  });
  const outcome = readFileSync(output, "utf8")
    .split("\n")
    .find((line) => line.startsWith("outcome="))
    ?.slice("outcome=".length);
  return {
    ...result,
    outcome,
    git,
    midRebase: existsSync(join(checkout, ".git", "rebase-merge")),
  };
};

describe("the rebase with a script", () => {
  it("rebases a branch whose changes do not touch main's", () => {
    const { status, outcome, git } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [["other.txt", "someone else's work"]],
    });

    expect(status).toBe(0);
    expect(outcome).toBe("rebased");
    expect(git("rev-parse", "--abbrev-ref", "HEAD")).toBe("feature");
    expect(git("log", "--format=%s", "origin/main..HEAD")).toBe(
      "feature.txt: the feature"
    );
  });

  it("stops mid-rebase on a conflict, for the agent to pick up", () => {
    const { status, outcome, midRebase } = rebase({
      onTheBranch: [["README.md", "the branch's start"]],
      onMainSince: [["README.md", "main's start"]],
    });

    expect(status).toBe(0);
    expect(outcome).toBe("conflicts");
    expect(midRebase).toBe(true);
  });

  it("leaves a branch already on top of main", () => {
    const { outcome } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [],
    });

    expect(outcome).toBe("up-to-date");
  });

  it("calls a branch whose changes are all on main superseded", () => {
    const { outcome } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [["feature.txt", "the feature"]],
    });

    expect(outcome).toBe("superseded");
  });
});
