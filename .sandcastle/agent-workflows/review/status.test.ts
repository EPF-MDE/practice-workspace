import { describe, expect, it } from "vitest";
import { reviewStatus } from "./status";

const verdict = (standards: string, spec: string) =>
  `## Standards: ${standards}\nOne line.\n\n## Spec: ${spec}\nMet.\n\n## Rules this review wanted and could not find\n- None.\n`;

describe("reviewStatus", () => {
  it("passes a verdict that passes both axes and leaves no finding", () => {
    expect(reviewStatus(verdict("PASS", "PASS"), 0).state).toBe("success");
  });

  it("fails a verdict that requests changes on either axis", () => {
    expect(reviewStatus(verdict("CHANGES REQUESTED", "PASS"), 0).state).toBe(
      "failure"
    );
    expect(reviewStatus(verdict("PASS", "CHANGES REQUESTED"), 0).state).toBe(
      "failure"
    );
  });

  it("fails a passing verdict that still left a finding", () => {
    expect(reviewStatus(verdict("PASS", "PASS"), 2)).toEqual({
      state: "failure",
      description: "The review left 2 findings for a person.",
    });
  });

  it("fails a run with no verdict", () => {
    expect(reviewStatus(undefined, 0).state).toBe("failure");
  });

  it("fails a verdict missing an axis", () => {
    expect(reviewStatus("## Standards: PASS\nOne line.\n", 0).state).toBe(
      "failure"
    );
  });
});
