// Fails when a workflow hands the agent's own secrets to a step that does not
// run the agent, or hands a step every secret at once. Why: #503, story 36
// and "Added on top: PostHog". The agent's step is the one that runs a script
// in .sandcastle/agent-workflows/.
// Usage: node scripts/check-agent-secrets.js <workflow file>...

import { readFileSync } from "node:fs";
import { parse } from "yaml";

const AGENT_ONLY = ["CLAUDE_CODE_OAUTH_TOKEN", "POSTHOG_API_KEY"];

// The agent-only secrets an `env` map sets or reads.
const agentSecretsIn = (env) =>
  AGENT_ONLY.filter((name) => JSON.stringify(env ?? {}).includes(name));

const ALL_SECRETS = /tojson\(\s*secrets\s*\)/i;

const handsOutEverySecret = (value) =>
  ALL_SECRETS.test(JSON.stringify(value ?? {}));

const runsTheAgent = (step) =>
  String(step.run ?? "").includes(".sandcastle/agent-workflows/");

const leaksIn = (file) => {
  const { jobs = {}, ...workflow } = parse(readFileSync(file, "utf8")) ?? {};
  const leaks = agentSecretsIn(workflow.env).map(
    (name) => `${file}: ${name} in the workflow's env`
  );
  if (handsOutEverySecret(workflow)) {
    leaks.push(`${file}: toJSON(secrets) in the workflow`);
  }
  for (const [id, { steps = [], ...job }] of Object.entries(jobs)) {
    for (const name of agentSecretsIn(job.env)) {
      leaks.push(`${file}: ${name} in job "${id}", its env`);
    }
    if (handsOutEverySecret(job)) {
      leaks.push(`${file}: toJSON(secrets) in job "${id}"`);
    }
    for (const step of steps) {
      const where = `job "${id}", step "${step.name ?? step.uses}"`;
      if (handsOutEverySecret(step)) {
        leaks.push(`${file}: toJSON(secrets) in ${where}`);
      }
      if (runsTheAgent(step)) continue;
      for (const name of agentSecretsIn(step.env)) {
        leaks.push(`${file}: ${name} in ${where}`);
      }
    }
  }
  return leaks;
};

const leaks = process.argv.slice(2).flatMap(leaksIn);

if (leaks.length > 0) {
  console.error(
    "These secrets belong on the agent's step only, and no step gets them all:\n"
  );
  for (const leak of leaks) {
    console.error(`  ${leak}`);
  }
  console.error(`
Move each one into the env of the step that runs the agent (the one running
.sandcastle/agent-workflows/), and nowhere else. Name each secret a step
needs instead of toJSON(secrets).`);
  process.exit(1);
}
