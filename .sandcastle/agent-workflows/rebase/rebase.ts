import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { claudeAgent, required } from "../shared/common";

const SITUATIONS = {
  conflicts:
    "The rebase stopped on conflicts. `git status` shows the commit it stopped at and the conflicted files.",
  rebased:
    "The rebase went through, but `npm run check` fails on the result: the base changed something the pull request relies on. /tmp/check.log holds the output.",
} as const;

const situation = required("SITUATION");
if (!(situation in SITUATIONS)) {
  throw new Error(
    `SITUATION is "${situation}": the agent resolves only ${Object.keys(SITUATIONS).join(" or ")}.`
  );
}

await sandcastle.run({
  name: "rebase",
  agent: claudeAgent(),
  sandbox: noSandbox(),
  logging: { type: "stdout" },
  promptFile: path.join(import.meta.dirname, "prompt.md"),
  promptArgs: {
    PR_NUMBER: required("PR_NUMBER"),
    BRANCH: required("BRANCH"),
    BASE_REF: required("BASE_REF"),
    SITUATION: SITUATIONS[situation as keyof typeof SITUATIONS],
  },
});
