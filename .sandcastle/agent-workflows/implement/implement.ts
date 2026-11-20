// Copied from the Software Factories cohort (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30, .sandcastle/agent-workflows/implement/implement.ts.

import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { claudeAgent } from "../shared/common";

// The agent edits files and commits them itself, so the repo's pre-commit
// hook runs on its work and it has to fix whatever the hook rejects. It does
// not push or open the PR, and it holds no GitHub token to do either — the
// workflow steps after this one do, where you can read them.
await sandcastle.run({
  name: "implement",
  agent: claudeAgent(),
  sandbox: noSandbox(),
  logging: { type: "stdout" },
  promptFile: path.join(import.meta.dirname, "prompt.md"),
});
