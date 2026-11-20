// Fails when a workflow hands the agent's own secrets to a step that does not
// run the agent. POSTHOG_API_KEY goes on the agent's step only (#503, "Added
// on top: PostHog"): a job's or a workflow's env would give it to every step.
// The agent's step is the one that runs a script in .sandcastle/agent-workflows/.
// Usage: node scripts/check-agent-secrets.js <workflow file>...

import { readFileSync } from "node:fs";
import { parse } from "yaml";

const AGENT_ONLY = ["POSTHOG_API_KEY"];

const holds = (value) =>
  AGENT_ONLY.filter((name) => JSON.stringify(value ?? {}).includes(name));

const runsTheAgent = (step) =>
  String(step.run ?? "").includes(".sandcastle/agent-workflows/");

const leaksIn = (file) => {
  const workflow = parse(readFileSync(file, "utf8")) ?? {};
  const leaks = holds(workflow.env).map(
    (name) => `${file}: ${name} in the workflow's env`
  );
  for (const [id, job] of Object.entries(workflow.jobs ?? {})) {
    for (const name of holds(job.env)) {
      leaks.push(`${file}: ${name} in job "${id}", its env`);
    }
    for (const step of job.steps ?? []) {
      if (runsTheAgent(step)) continue;
      for (const name of holds(step)) {
        leaks.push(
          `${file}: ${name} in job "${id}", step "${step.name ?? step.uses}"`
        );
      }
    }
  }
  return leaks;
};

const leaks = process.argv.slice(2).flatMap(leaksIn);

if (leaks.length > 0) {
  console.error("These secrets belong on the agent's step only:\n");
  for (const leak of leaks) {
    console.error(`  ${leak}`);
  }
  console.error(`
Move each one into the env of the step that runs the agent (the one running
.sandcastle/agent-workflows/), and nowhere else.`);
  process.exit(1);
}
