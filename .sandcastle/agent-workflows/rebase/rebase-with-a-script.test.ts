import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { stepScript } from "../shared/step-script";
import { SITUATIONS } from "./situations";

const rebaseWithAScript = stepScript(
  "agent-rebase.yml",
  "rebase",
  "Rebase with a script"
);

const WORKFLOW = readFileSync(
  join(import.meta.dirname, "../../../.github/workflows/agent-rebase.yml"),
  "utf8"
);

const wordsIn = (text: string, pattern: RegExp): Set<string> =>
  new Set([...text.matchAll(pattern)].map(([, word]) => word as string));

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
  commit: (file: string, text: string, by = "the branch") => {
    writeFileSync(join(dir, file), text);
    execFileSync("git", ["add", file], { cwd: dir });
    execFileSync("git", ["commit", "-qm", `${file}: ${text}, by ${by}`], {
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
  for (const [file, text] of onMainSince) commit(file, text, "main");
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

describe("the rebase with a script", { timeout: 20_000 }, () => {
  it("rebases a branch whose changes do not touch main's", () => {
    const { status, outcome, git } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [["other.txt", "someone else's work"]],
    });

    expect(status).toBe(0);
    expect(outcome).toBe("rebased");
    expect(git("rev-parse", "--abbrev-ref", "HEAD")).toBe("feature");
    expect(git("log", "--format=%s", "origin/main..HEAD")).toBe(
      "feature.txt: the feature, by the branch"
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

describe("the outcomes of the rebase with a script", () => {
  const written = wordsIn(rebaseWithAScript, /outcome=([a-z-]+)/g);

  it("are the outcomes the workflow handles, each spelt the same", () => {
    const handled = new Set([
      ...wordsIn(WORKFLOW, /steps\.script\.outputs\.outcome == '([a-z-]+)'/g),
      ...wordsIn(WORKFLOW, /"\$OUTCOME" = "([a-z-]+)"/g),
    ]);

    expect(written).toEqual(
      new Set(["up-to-date", "superseded", "rebased", "conflicts"])
    );
    expect(handled).toEqual(written);
  });

  it("give the agent only situations it knows", () => {
    const agentSituations = wordsIn(
      WORKFLOW.slice(WORKFLOW.indexOf("SITUATION:")).split("\n")[0] ?? "",
      /'([a-z-]+)'/g
    );
    agentSituations.delete("failure");

    expect(agentSituations).toEqual(new Set(["check-fails"]));
    for (const situation of Object.keys(SITUATIONS)) {
      expect([...agentSituations, ...written]).toContain(situation);
    }
  });
});
