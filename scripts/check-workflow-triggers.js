// Fails when a workflow runs on a trigger that gives a fork's code the
// repository's secrets: pull_request_target and workflow_run both run in the
// base repository's context, with its secrets and a write token. On
// pull_request, GitHub gives a fork's pull request neither. Why: #509 in
// EPF-MDE/complex-web-services.
// Usage: node scripts/check-workflow-triggers.js <workflow file>...

import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "yaml";

const FORBIDDEN = ["pull_request_target", "workflow_run"];

// `on` is a string, a list or a map of triggers.
const triggersOf = (on) => {
  if (typeof on === "string") return [on];
  if (Array.isArray(on)) return on;
  return Object.keys(on ?? {});
};

const forbiddenIn = (file) => {
  const { on } = parse(readFileSync(file, "utf8")) ?? {};
  return triggersOf(on)
    .filter((trigger) => FORBIDDEN.includes(trigger))
    .map((trigger) => `${basename(file)}: ${trigger}`);
};

const found = process.argv.slice(2).flatMap(forbiddenIn);

if (found.length > 0) {
  console.error(
    "These workflows run on a trigger that gives a fork's code the secrets:\n"
  );
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
Trigger them on pull_request instead, where a fork's pull request gets the
check and no secret.`);
  process.exit(1);
}
