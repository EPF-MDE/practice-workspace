// The token check, run as the hook and `npm run check` run it: on the paths
// git lists, from the repository's root.

import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-file-tokens.js");

const checkIn = (files, paths) => {
  const root = mkdtempSync(join(tmpdir(), "check-file-tokens-"));
  for (const [file, contents] of Object.entries(files)) {
    writeFileSync(join(root, file), contents);
  }
  mkdirSync(join(root, "skills"));
  symlinkSync("skills", join(root, "linked-skills"));
  return spawnSync("node", [script, ...paths], {
    cwd: root,
    encoding: "utf8",
  });
};

describe("check-file-tokens", () => {
  it("passes a symlink to a directory, as git lists .agents/skills", () => {
    const result = checkIn({ "small.md": "A line.\n" }, [
      "small.md",
      "linked-skills",
    ]);

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("still refuses a file over 5000 tokens beside such a symlink", () => {
    const result = checkIn({ "big.md": "x".repeat(20_004) }, [
      "linked-skills",
      "big.md",
    ]);

    expect(result.stderr).toContain("big.md: ~5001 tokens");
    expect(result.status).toBe(1);
  });
});
