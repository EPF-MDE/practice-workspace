import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

export const repositoryWith = (files) => {
  const root = mkdtempSync(join(tmpdir(), "check-"));
  for (const [file, contents] of Object.entries(files)) {
    mkdirSync(join(root, dirname(file)), { recursive: true });
    writeFileSync(join(root, file), contents);
  }
  return root;
};

export const checkOn = (command, script, files) =>
  spawnSync(command, [script, ...Object.keys(files)], {
    cwd: repositoryWith(files),
    encoding: "utf8",
  });
