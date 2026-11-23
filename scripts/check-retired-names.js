import { readFileSync, statSync } from "node:fs";

const RETIRED = [
  {
    name: "Practice Plan",
    now: "Evidence Plan",
    pattern: /practice[\s_-]*plan/i,
  },
  {
    name: "fork reading",
    now: "Repository reading",
    pattern: /fork[\s_-]*reading/i,
  },
  { name: "fork panel", now: "Evidence panel", pattern: /fork[\s_-]*panel/i },
];

const ALLOWED = new Set([
  "GLOSSARY.md",
  "scripts/check-retired-names.js",
  "scripts/check-retired-names.test.js",
]);

const retiredIn = (file) => {
  if (ALLOWED.has(file) || !statSync(file).isFile()) return [];
  const text = readFileSync(file, "utf8");
  if (text.includes("\0")) return [];
  return text
    .split("\n")
    .flatMap((line, index) =>
      RETIRED.filter(({ pattern }) => pattern.test(line)).map(
        ({ name, now }) => `${file}:${index + 1}: ${name}, now ${now}`
      )
    );
};

const found = process.argv.slice(2).flatMap(retiredIn);

if (found.length > 0) {
  console.error("These lines use a name the glossary retired:\n");
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
Use the glossary's name instead. Only GLOSSARY.md names a retired one, on its
Avoid list.`);
  process.exit(1);
}
