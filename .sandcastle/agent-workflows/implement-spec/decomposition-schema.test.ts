import { describe, expect, it } from "vitest";
import { specDecompositionSchema } from "./decomposition-schema";

const queue = (length: number) => ({
  tickets: Array.from({ length }, (_, i) => ({
    position: i + 1,
    title: `Ticket ${i + 1}`,
    body: "## What\n\nIt.\n\n## Done when\n\nIt is.",
    shape: "service-module",
    depends_on: i === 0 ? [] : [i],
  })),
});

describe("specDecompositionSchema", () => {
  it("takes a queue of 12 tickets", () => {
    expect(specDecompositionSchema.safeParse(queue(12)).success).toBe(true);
  });

  it("refuses a 13th ticket, so a spec stops at 12", () => {
    expect(specDecompositionSchema.safeParse(queue(13)).success).toBe(false);
  });

  it("refuses an empty queue", () => {
    expect(specDecompositionSchema.safeParse(queue(0)).success).toBe(false);
  });
});
