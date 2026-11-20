// From the Software Factories for Real Engineers cohort
// (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30.

import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { claudeAgent } from "../shared/common";

// Like the one-off implementer: the agent edits and commits, through the
// pre-commit hook; the workflow pushes and opens the PR.
await sandcastle.run({
  name: "build-ticket",
  agent: claudeAgent(),
  sandbox: noSandbox(),
  logging: { type: "stdout" },
  promptFile: path.join(import.meta.dirname, "build-prompt.md"),
});
