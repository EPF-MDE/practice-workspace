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
  atTheStart?: [file: string, text: string][];
  onTheBranch: [file: string, text: string][];
  onMainSince: [file: string, text: string][];
};

const rebase = ({ atTheStart = [], onTheBranch, onMainSince }: Story) => {
  const dir = mkdtempSync(join(tmpdir(), "rebase-"));
  const origin = join(dir, "origin.git");
  const checkout = join(dir, "checkout");
  execFileSync("git", ["init", "-q", "--bare", "-b", "main", origin]);
  execFileSync("git", ["clone", "-q", origin, checkout]);
  const { git, commit } = inRepository(checkout);
  git("checkout", "-qb", "main");
  commit("README.md", "the start");
  for (const [file, text] of atTheStart) commit(file, text, "main");
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
  const written = readFileSync(output, "utf8").split("\n");
  const valueOf = (name: string) =>
    written
      .find((line) => line.startsWith(`${name}=`))
      ?.slice(`${name}=`.length);
  return {
    ...result,
    outcome: valueOf("outcome"),
    diff: valueOf("diff"),
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

const TWENTY_LINES = Array.from(
  { length: 20 },
  (_, index) => `line ${index + 1}`
);

const withLine = (line: number, text: string) =>
  TWENTY_LINES.map((each, index) => (index === line - 1 ? text : each)).join(
    "\n"
  );

describe("the rebase with a script, on the diff the review read", {
  timeout: 20_000,
}, () => {
  it("calls the diff unchanged when main changed other files", () => {
    const { outcome, diff } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [["other.txt", "someone else's work"]],
    });

    expect(outcome).toBe("rebased");
    expect(diff).toBe("unchanged");
  });

  it("calls the diff unchanged when main changed the same file far from it", () => {
    const { outcome, diff } = rebase({
      atTheStart: [["lines.txt", withLine(1, "line 1")]],
      onTheBranch: [["lines.txt", withLine(18, "the branch's line 18")]],
      onMainSince: [["lines.txt", withLine(2, "main's line 2")]],
    });

    expect(outcome).toBe("rebased");
    expect(diff).toBe("unchanged");
  });

  it("calls the diff changed when main changed a line beside it", () => {
    const { outcome, diff } = rebase({
      atTheStart: [["lines.txt", withLine(1, "line 1")]],
      onTheBranch: [["lines.txt", withLine(6, "the branch's line 6")]],
      onMainSince: [["lines.txt", withLine(4, "main's line 4")]],
    });

    expect(outcome).toBe("rebased");
    expect(diff).toBe("changed");
  });

  it("says nothing of the diff when nothing was rebased", () => {
    const { outcome, diff } = rebase({
      onTheBranch: [["feature.txt", "the feature"]],
      onMainSince: [],
    });

    expect(outcome).toBe("up-to-date");
    expect(diff).toBeUndefined();
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

  it("say whether the diff changed in the words the review's decision reads", () => {
    expect(wordsIn(rebaseWithAScript, /diff=([a-z]+)/g)).toEqual(
      new Set(["unchanged", "changed"])
    );
    expect(wordsIn(WORKFLOW, /"\$DIFF" != "([a-z]+)"/g)).toEqual(
      new Set(["unchanged"])
    );
  });

  it("lead to a review decision spelt as the steps after it read it", () => {
    expect(wordsIn(WORKFLOW, /review=([a-z]+) because=/g)).toEqual(
      new Set(["keep", "request"])
    );
    expect(wordsIn(WORKFLOW, /"\$REVIEW" [!=]+ "([a-z]+)"/g)).toEqual(
      new Set(["keep"])
    );
  });

  it("give the report a reason spelt as the decision wrote it", () => {
    const reasons = wordsIn(WORKFLOW, /because=([a-z]+)$/gm);
    expect(reasons).toEqual(
      new Set(["agent", "waiting", "changed", "unchanged"])
    );
    for (const read of wordsIn(WORKFLOW, /"\$BECAUSE" = "([a-z]+)"/g)) {
      expect(reasons).toContain(read);
    }
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
