import { z } from "zod/v4";

export const reviewSchema = z
  .strictObject({
    comments: z
      .array(
        z.strictObject({
          axis: z
            .enum(["standards", "spec"])
            .describe("The verdict section the finding belongs to."),
          title: z
            .string()
            .min(1)
            .describe(
              "The finding in a few words, plain text, e.g. 'Server module imports a UI component'."
            ),
          path: z
            .string()
            .min(1)
            .describe("The file, relative to the repository root."),
          line: z
            .number()
            .int()
            .positive()
            .describe(
              "A line in the file as it is now, inside a hunk of the diff against the base. A comment outside the hunks goes into the verdict instead."
            ),
          body: z
            .string()
            .min(1)
            .describe(
              "The finding, in Markdown: the rule or spec line it breaks, why it could not be fixed here, and what to do instead."
            ),
        })
      )
      .describe(
        "One entry per finding you left unfixed, on the first line it concerns. Empty is fine."
      ),
    applied: z
      .array(
        z.strictObject({
          thread: z
            .number()
            .int()
            .positive()
            .describe(
              "The id of an answered thread in /tmp/review-threads.md."
            ),
          commit: z
            .string()
            .regex(/^[0-9a-f]{7,40}$/)
            .nullable()
            .describe(
              "The commit of yours that applies the answer, or null when the answer needs no change to the branch."
            ),
          summary: z
            .string()
            .min(1)
            .describe(
              "One plain sentence saying what you did with the answer, for the person who gave it."
            ),
        })
      )
      .describe(
        "One entry per answered thread you applied. The workflow replies on each thread with it. Empty is fine."
      ),
  })
  .describe("The review's inline comments, and the answers it applied.");

export type ReviewComment = z.infer<typeof reviewSchema>["comments"][number];
