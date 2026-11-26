import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "yaml";

const WRITER = "warm-caches.yml";
const READER = /^agent-.*\.yml$/;

const lines = (value) =>
  String(value ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .sort()
    .join(", ");

const cacheOf = (step) => {
  const action = String(step.uses ?? "").split("@")[0];
  const given = step.with ?? {};
  if (action === "actions/setup-node" && given.cache === "npm") {
    return { cache: "npm", key: lines(given["cache-dependency-path"]) };
  }
  if (action === "astral-sh/setup-uv" && given["enable-cache"]) {
    return { cache: "uv", key: lines(given["cache-dependency-glob"]) };
  }
  if (action === "actions/cache") {
    return { cache: lines(given.path), key: String(given.key) };
  }
  return undefined;
};

const keysIn = (file) => {
  const { jobs } = parse(readFileSync(file, "utf8")) ?? {};
  return Object.entries(jobs ?? {}).flatMap(([name, job]) =>
    (job.steps ?? []).flatMap((step, index) => {
      const read = cacheOf(step);
      const where = `${basename(file)}: job ${name}, step ${step.name ?? index + 1}`;
      return read ? [{ where, ...read }] : [];
    })
  );
};

const problemOf = (written, { where, cache, key }) => {
  if (!written.has(cache)) {
    return `${where} reads the ${cache} cache, which ${WRITER} does not write`;
  }
  if (written.get(cache) !== key) {
    return `${where} reads the ${cache} cache under "${key}", ${WRITER} writes "${written.get(cache)}"`;
  }
  return undefined;
};

const problemsIn = (files) => {
  const writer = files.find((file) => basename(file) === WRITER);
  if (writer === undefined)
    return [`${WRITER} is not among the workflows checked`];
  const written = new Map(keysIn(writer).map(({ cache, key }) => [cache, key]));
  return files
    .filter((file) => READER.test(basename(file)))
    .flatMap(keysIn)
    .map((read) => problemOf(written, read))
    .filter(Boolean);
};

const found = problemsIn(process.argv.slice(2));

if (found.length > 0) {
  console.error("These agent workflows look up a cache that nobody writes:\n");
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
An agent job only reads the caches, and ${WRITER} alone writes them, on main
(ADR-0019). Give the step the key ${WRITER} writes, or write the new key there.`);
  process.exit(1);
}
