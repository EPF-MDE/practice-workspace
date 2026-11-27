import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "yaml";

const WRITER = "warm-caches.yml";
const READER = /^agent-.*\.yml$/;

const sortedList = (value) =>
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
    return { cache: "npm", key: sortedList(given["cache-dependency-path"]) };
  }
  if (
    action === "astral-sh/setup-uv" &&
    String(given["enable-cache"]) !== "false"
  ) {
    return { cache: "uv", key: sortedList(given["cache-dependency-glob"]) };
  }
  if (action === "actions/cache" || action.startsWith("actions/cache/")) {
    return {
      cache: sortedList(given.path),
      key: String(given.key),
      saves: action !== "actions/cache/restore",
      restores: action !== "actions/cache/save",
    };
  }
  return undefined;
};

const keysIn = (file) => {
  const { jobs } = parse(readFileSync(file, "utf8")) ?? {};
  return Object.entries(jobs ?? {}).flatMap(([name, job]) =>
    (job.steps ?? []).flatMap((step, index) => {
      const cache = cacheOf(step);
      const where = `${basename(file)}: job ${name}, step ${step.name ?? index + 1}`;
      return cache ? [{ where, saves: true, restores: true, ...cache }] : [];
    })
  );
};

const problemOf = (written, { where, cache, key, restores }) => {
  if (!restores) {
    return `${where} saves the ${cache} cache, which only ${WRITER} writes`;
  }
  if (!written.has(cache)) {
    return `${where} reads the ${cache} cache, which ${WRITER} does not write`;
  }
  if (!written.get(cache).has(key)) {
    const keys = [...written.get(cache)].map((one) => `"${one}"`).join(" or ");
    return `${where} reads the ${cache} cache under "${key}", ${WRITER} writes ${keys}`;
  }
  return undefined;
};

const keysWrittenBy = (writer) => {
  const written = new Map();
  for (const { cache, key } of keysIn(writer).filter(({ saves }) => saves)) {
    written.set(cache, (written.get(cache) ?? new Set()).add(key));
  }
  return written;
};

const problemsIn = (files) => {
  const writer = files.find((file) => basename(file) === WRITER);
  if (writer === undefined)
    return [`${WRITER} is not among the workflows checked`];
  const written = keysWrittenBy(writer);
  return files
    .filter((file) => READER.test(basename(file)))
    .flatMap(keysIn)
    .map((read) => problemOf(written, read))
    .filter(Boolean);
};

const found = problemsIn(process.argv.slice(2));

if (found.length > 0) {
  console.error(
    `These agent workflows do not read a cache that ${WRITER} writes:\n`
  );
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
An agent job only reads the caches, and ${WRITER} alone writes them, on main
(ADR-0019). Give the step the key ${WRITER} writes, or write the new key there;
an agent job that saves a cache restores it instead.`);
  process.exit(1);
}
