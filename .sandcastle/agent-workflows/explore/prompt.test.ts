import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const prompt = readFileSync(new URL("./prompt.md", import.meta.url), "utf8");
const blastRadius = prompt
  .split("\n")
  .find((line) => line.includes("the blast radius"));

describe("the explore prompt's blast radius", () => {
  it("names this repository's Deep Modules and the Store", () => {
    expect(blastRadius).toContain("backend/app");
    expect(blastRadius).toContain("frontend/src/packages");
    expect(blastRadius).toContain("the Store");
  });

  it("no longer names the cohort's layout", () => {
    expect(blastRadius).not.toContain("app/modules/");
    expect(blastRadius).not.toContain("tables");
  });
});
