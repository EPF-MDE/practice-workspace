import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { claudeAgent, required } from "../shared/common";
import { isSituation, SITUATIONS } from "./situations";

const situation = required("SITUATION");
if (!isSituation(situation)) {
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
    SITUATION: SITUATIONS[situation],
  },
});
