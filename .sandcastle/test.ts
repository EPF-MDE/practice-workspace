// Copied from the Software Factories cohort (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30, .sandcastle/test.ts.

import { run, claudeCode } from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

await run({
  agent: claudeCode("claude-opus-5-5"),
  sandbox: docker(),
  prompt: "Hello, how are you?",
});
