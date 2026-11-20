import { z } from "zod/v4";

export const extractionPrompt = (tag: string, schema: z.ZodType): string =>
  [
    `Reply with one \`<${tag}>\` block and nothing else. Inside it, put one JSON value that matches this JSON Schema:`,
    "",
    "```json",
    JSON.stringify(z.toJSONSchema(schema), null, 2),
    "```",
    "",
    "Answer from what you have already read, with no tool calls.",
    "",
    `<${tag}>`,
    "{ ...the JSON value... }",
    `</${tag}>`,
  ].join("\n");
