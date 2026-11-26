import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "yaml";

const FORBIDDEN = ["workflow_run"];
const RUNS_ONLY_GH = "pull_request_target";
const SAME_REPOSITORY =
  "github.event.pull_request.head.repo.full_name == github.repository";

const triggersOf = (on) => {
  if (typeof on === "string") return [on];
  if (Array.isArray(on)) return on;
  return Object.keys(on ?? {});
};

const conjunctsOf = (condition) => {
  const conjuncts = [""];
  let depth = 0;
  for (let at = 0; at < condition.length; at += 1) {
    const char = condition[at];
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (depth === 0 && condition.startsWith("||", at)) return [];
    if (depth === 0 && condition.startsWith("&&", at)) {
      conjuncts.push("");
      at += 1;
    } else {
      conjuncts[conjuncts.length - 1] += char;
    }
  }
  return conjuncts.map((conjunct) => conjunct.trim());
};

const skipsForks = (condition) =>
  conjunctsOf(
    String(condition ?? "")
      .trim()
      .replace(/^\$\{\{([\s\S]*)\}\}$/, "$1")
  ).includes(SAME_REPOSITORY);

const codeRunIn = (name, job) => {
  const found = [];
  if (!skipsForks(job.if)) {
    found.push(`job ${name} does not skip a fork's pull request`);
  }
  if (job.uses) found.push(`job ${name} calls a workflow`);
  for (const [index, step] of (job.steps ?? []).entries()) {
    const where = `job ${name}, step ${step.name ?? index + 1}`;
    const run = String(step.run ?? "");
    if (step.uses) found.push(`${where} uses an action`);
    if (/\bgit\b/.test(run)) found.push(`${where} calls git`);
    if (/checkout/.test(run)) found.push(`${where} checks out code`);
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
  const codeRun = triggers.includes(RUNS_ONLY_GH)
    ? Object.entries(jobs ?? {}).flatMap(([name, job]) =>
        codeRunIn(name, job).map(
          (problem) => `${basename(file)}: ${RUNS_ONLY_GH}, ${problem}`
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
request, use no action, call no git, check out nothing and interpolate no expression in a
script (ADR-0017).`);
  process.exit(1);
}
