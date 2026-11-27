import { z } from "zod/v4";

export const explorePlanSchema = z
  .strictObject({
    issues: z
      .array(
        z.strictObject({
          number: z.number().int().describe("The issue this entry is for."),
          tag: z
            .enum(["easy-call", "needs-a-human", "blocked"])
            .describe(
              "The call. A duplicate takes the tag of the issue it duplicates."
            ),
          duplicate_of: z
            .number()
            .int()
            .optional()
            .describe(
              "Only on a duplicate: the oldest issue in the batch it duplicates. That issue survives. Leave it out when this issue survives."
            ),
          blocked_by: z
            .array(z.number().int())
            .optional()
            .describe(
              "Only on a survivor tagged `blocked`, and required there: the open issues of this repository it waits on, by number. The workflow marks them as its blockers on GitHub, and sends the issue back to explore once they are all closed."
            ),
          decision: z
            .strictObject({
              question: z
                .string()
                .min(1)
                .describe(
                  "The one decision a person has to make, as a question."
                ),
              options: z
                .array(z.string().min(1))
                .min(2)
                .describe(
                  "The answers to choose from, each with what it costs."
                ),
            })
            .optional()
            .describe(
              "Only on a survivor tagged `needs-a-human`, and required there. The workflow posts it at the end of the comment."
            ),
          comment: z
            .string()
            .min(1)
            .describe("The Markdown comment to post on the issue, as-is."),
        })
      )
      .describe("One entry per issue in the batch. Every issue exactly once."),
  })
  .describe("The explore plan.");
