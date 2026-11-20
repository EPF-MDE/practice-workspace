// From the Software Factories for Real Engineers cohort
// (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30.

import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { claudeAgent, writeJson } from "../shared/common";
import { extractionPrompt } from "../shared/extraction-prompt";
import { runWithExtraction } from "../shared/run-with-extraction";
import { specDecompositionSchema } from "./decomposition-schema";

// This loop writes tickets, not code, and the workflow step after this one is
// what actually creates them.
const result = await runWithExtraction({
  name: "decompose",
  agent: claudeAgent(),
  sandbox: noSandbox(),
  logging: { type: "stdout" },
  promptFile: path.join(import.meta.dirname, "decompose-prompt.md"),
  output: sandcastle.Output.object({
    tag: "queue",
    schema: specDecompositionSchema,
  }),
  extractionPrompt: extractionPrompt("queue", specDecompositionSchema),
});

writeJson("queue.json", result.output);
