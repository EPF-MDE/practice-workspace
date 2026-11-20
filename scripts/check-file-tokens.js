// Fails when a file is too big for an agent to read and edit in one go.
// Copied from the Software Factories cohort's setup
// (https://github.com/ai-hero-dev/cohort-005-project, scripts/check-file-tokens.js).
// Tokens are estimated as bytes / 4, which is close enough for code.
// Usage: node scripts/check-file-tokens.js <file>...

import { lstatSync, readFileSync } from "node:fs";

const MAX_TOKENS = 5000;
const BYTES_PER_TOKEN = 4;

// Generated files that nobody edits by hand, and workflow files, which
// GitHub reads as one file each and which cannot be split.
const IGNORED = [
  /(^|\/)package-lock\.json$/,
  /(^|\/)uv\.lock$/,
  /^\.github\/workflows\/[^/]+\.yml$/,
];

// git lists a symlink as one path, such as .claude/skills, a link to
// .agents/skills. Its target is checked on its own path, so only regular
// files are read.
const isRegularFile = (file) => lstatSync(file).isFile();

const isBinary = (contents) => contents.subarray(0, 8000).includes(0);

const oversized = process.argv
  .slice(2)
  .map((file) => file.replaceAll("\\", "/").replace(`${process.cwd()}/`, ""))
  .filter((file) => !IGNORED.some((pattern) => pattern.test(file)))
  .filter(isRegularFile)
  .map((file) => ({ file, contents: readFileSync(file) }))
  .filter(({ contents }) => !isBinary(contents))
  .map(({ file, contents }) => ({
    file,
    tokens: Math.ceil(contents.length / BYTES_PER_TOKEN),
  }))
  .filter(({ tokens }) => tokens > MAX_TOKENS);

if (oversized.length > 0) {
  console.error(`These files are over ${MAX_TOKENS} tokens (bytes / 4):\n`);
  for (const { file, tokens } of oversized) {
    console.error(`  ${file}: ~${tokens} tokens`);
  }
  console.error(`
Split each file before you commit. Do not delete code or squash it onto fewer
lines to get under the limit.

How to split:
- Find the seams. Look for groups of functions, components, or tests that
  change together and share little with the rest of the file.
- A module of the back end (backend/app/<name>/): split it into more private
  files (named with a leading "_") behind the module's __init__.py, which
  stays small.
- Front-end components: move sub-components into their own files, and logic
  out of the component into a plain module beside it.
- Tests: split by the behaviour under test, one file per area. Move shared
  fixtures into conftest.py or a fixtures file in the same folder.
- Scripts and data: move large data literals into their own files.

When you are done, run \`npm run check\` and commit again.`);
  process.exit(1);
}
