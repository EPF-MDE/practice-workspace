// Copied from the Software Factories cohort (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30, .sandcastle/interactive.ts.

import { claudeCode, interactive } from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";

await interactive({
  agent: claudeCode("claude-opus-5-5"),
  sandbox: noSandbox(),
  promptFile: "./.sandcastle/prompt.md",
});
