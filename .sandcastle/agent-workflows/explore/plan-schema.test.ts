import { describe, expect, it } from "vitest";
import { explorePlanSchema } from "./plan-schema";

const plan = (entry: Record<string, unknown>) => ({
  issues: [{ number: 3, tag: "easy-call", comment: "Findings.", ...entry }],
});

describe("explorePlanSchema", () => {
  it("takes an entry for each tag the workflow branches on", () => {
    for (const tag of ["easy-call", "needs-a-human", "blocked"]) {
      expect(explorePlanSchema.safeParse(plan({ tag })).success).toBe(true);
    }
  });

  it("takes a duplicate pointing at the issue it duplicates", () => {
    expect(explorePlanSchema.safeParse(plan({ duplicate_of: 2 })).success).toBe(
      true
    );
  });

  it("refuses an unknown tag, an empty comment and an unknown key", () => {
    for (const entry of [
      { tag: "ship-it" },
      { comment: "" },
      { labels: ["agent:implement"] },
    ]) {
      expect(explorePlanSchema.safeParse(plan(entry)).success).toBe(false);
    }
  });
});
