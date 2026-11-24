import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parse } from "yaml";

type Step = { name?: string; run?: string };
type Workflow = { jobs: Record<string, { steps: Step[] }> };

export const stepScript = (file: string, job: string, step: string): string => {
  const workflow = parse(
    readFileSync(
      join(import.meta.dirname, "../../../.github/workflows", file),
      "utf8"
    )
  ) as Workflow;
  const run = workflow.jobs[job]?.steps.find(({ name }) => name === step)?.run;
  if (run === undefined) {
    throw new Error(`${file} has no step "${step}" in job "${job}".`);
  }
  return run;
};
