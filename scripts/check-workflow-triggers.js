import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "yaml";

const FORBIDDEN = ["workflow_run"];
const CODE_FREE = "pull_request_target";
const SAME_REPOSITORY =
  "github.event.pull_request.head.repo.full_name == github.repository";

const triggersOf = (on) => {
  if (typeof on === "string") return [on];
  if (Array.isArray(on)) return on;
  return Object.keys(on ?? {});
};

const codeRunIn = (name, job) => {
  const found = [];
  if (!String(job.if ?? "").includes(SAME_REPOSITORY)) {
    found.push(`job ${name} does not skip a fork's pull request`);
  }
  if (job.uses) found.push(`job ${name} calls a workflow`);
  for (const [index, step] of (job.steps ?? []).entries()) {
    const where = `job ${name}, step ${step.name ?? index + 1}`;
    const run = String(step.run ?? "");
    if (step.uses) found.push(`${where} uses an action`);
    if (/\bgit\b|checkout/.test(run)) found.push(`${where} calls git`);
    if (run.includes("${{")) found.push(`${where} interpolates an expression`);
  }
  return found;
};

const problemsIn = (file) => {
  const { on, jobs } = parse(readFileSync(file, "utf8")) ?? {};
  const triggers = triggersOf(on);
  const forbidden = triggers
    .filter((trigger) => FORBIDDEN.includes(trigger))
    .map((trigger) => `${basename(file)}: ${trigger}`);
  const codeRun = triggers.includes(CODE_FREE)
    ? Object.entries(jobs ?? {}).flatMap(([name, job]) =>
        codeRunIn(name, job).map(
          (problem) => `${basename(file)}: ${CODE_FREE}, ${problem}`
        )
      )
    : [];
  return [...forbidden, ...codeRun];
};

const found = process.argv.slice(2).flatMap(problemsIn);

if (found.length > 0) {
  console.error(
    "These workflows run on a trigger that gives a fork's code the secrets:\n"
  );
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
Trigger them on pull_request instead, where a fork's pull request gets the
check and no secret. A pull_request_target workflow must skip a fork's pull
request, use no action, call no git and interpolate no expression in a
script (ADR-0017).`);
  process.exit(1);
}
