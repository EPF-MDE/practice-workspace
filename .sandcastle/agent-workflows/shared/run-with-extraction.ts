import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  run,
  type OutputObjectDefinition,
  type RunOptions,
  type RunResult,
} from "@ai-hero/sandcastle";

export type RunWithExtractionOptions<T> = Omit<RunOptions, "output"> & {
  readonly output: OutputObjectDefinition<T>;
  readonly extractionPrompt: string;
  readonly maxRetries?: number;
};

export async function runWithExtraction<T>(
  options: RunWithExtractionOptions<T>
): Promise<RunResult & { output: T }> {
  const {
    output,
    extractionPrompt,
    maxRetries = 2,
    ...produceOptions
  } = options;

  if (!produceOptions.agent.sessionStorage) {
    return run({
      ...produceOptions,
      ...appendToPrompt(produceOptions, extractionPrompt),
      output: { ...output, maxRetries: 0 },
    });
  }

  const produce = await run(produceOptions);
  const sessionId = produce.iterations.at(-1)?.sessionId;

  if (!sessionId) {
    throw new Error(
      "Cannot extract structured output because the produce run had no session id."
    );
  }

  const { promptArgs: _promptArgs, ...extractionOptions } = produceOptions;
  const extractionOutput: OutputObjectDefinition<T> = {
    ...output,
    maxRetries,
  };
  const extraction = await run({
    ...extractionOptions,
    name: produceOptions.name ? `${produceOptions.name} (extract)` : undefined,
    promptFile: undefined,
    prompt: extractionPrompt,
    resumeSession: sessionId,
    output: extractionOutput,
  });

  return { ...produce, output: extraction.output };
}

const appendToPrompt = (
  options: Pick<RunOptions, "prompt" | "promptFile">,
  extractionPrompt: string
): Pick<RunOptions, "prompt" | "promptFile"> => {
  const suffix = [
    "",
    "",
    "When the task above is done, end with this final message. These rules bind that message only.",
    "",
    extractionPrompt,
  ].join("\n");

  if (options.promptFile === undefined) {
    return { prompt: `${options.prompt ?? ""}${suffix}` };
  }

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "run-with-extraction-"));
  const promptFile = path.join(dir, path.basename(options.promptFile));
  fs.writeFileSync(
    promptFile,
    `${fs.readFileSync(options.promptFile, "utf8")}${suffix}`
  );
  return { promptFile };
};
