// From the Software Factories for Real Engineers cohort
// (https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m),
// ai-hero-dev/cohort-005-project@4339a30.

import { z } from "zod/v4";

// The first loop's answer: one spec turned into an ordered queue of tickets.
// agent-implement-spec.yml creates one GitHub issue per entry, in `position`
// order, and the chain then works through them one at a time.
export const specDecompositionSchema = z
  .strictObject({
    tickets: z
      .array(
        z.strictObject({
          position: z
            .number()
            .int()
            .min(1)
            .describe(
              "Build order, starting at 1. The chain always takes the lowest open position whose dependencies are closed."
            ),
          title: z
            .string()
            .max(100)
            .describe(
              "The issue title. Say what the ticket delivers, not which layer it edits."
            ),
          body: z
            .string()
            .describe(
              "The ticket. Markdown, with a `## What` and a `## Done when` — the second is what the review workflow checks the pull request against, so it has to be checkable from a diff."
            ),
          shape: z
            .enum([
              "service-module",
              "route-only",
              "ui-only",
              "schema-change",
              "cross-cutting",
            ])
            .describe(
              "Where the ticket's change mostly lands. `service-module`: a rule, calculation or query behind a Deep Module's entry point, with its tests. `route-only`: a route, and nothing it calls changes. `ui-only`: components and what they render, no data change. `schema-change`: a format the Store keeps, with its contract tests. `cross-cutting`: more than one of these at once — usually a ticket worth splitting."
            ),
          depends_on: z
            .array(z.number().int().min(1))
            .describe(
              "Positions that must be finished first. Empty means it can be built the moment the queue opens — those are the ones that could run in parallel."
            ),
        })
      )
      .min(1)
      .max(12)
      .describe(
        "The queue, in build order. Keep it short. A queue longer than about eight is a spec that wanted decomposing into two specs."
      ),
  })
  .describe("The spec, cut into an ordered queue of tickets.");
