import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parse } from "yaml";

type Step = { name?: string; run?: string };
type Workflow = { jobs: Record<string, { steps: Step[] }> };

const workflow = parse(
  readFileSync(
    join(import.meta.dirname, "../../../.github/workflows/agent-rebase.yml"),
    "utf8"
  )
) as Workflow;

export const workflowStep = (job: string, name: string): string => {
  const run = workflow.jobs[job]?.steps.find((step) => step.name === name)?.run;
  if (run === undefined) {
    throw new Error(`agent-rebase.yml has no step "${name}" in job "${job}".`);
  }
  return run;
};
