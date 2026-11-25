import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import * as sandcastle from "@ai-hero/sandcastle";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { z } from "zod/v4";
import { claudeAgent, required, writeJson } from "../shared/common";
import { extractionPrompt } from "../shared/extraction-prompt";
import { runWithExtraction } from "../shared/run-with-extraction";
import { diffLines } from "./diff-lines";
import { addLeftFindings } from "./left-findings";
import { reviewSchema } from "./review-schema";
import { reviewStatus } from "./status";
import { repliesToAnswers, reviewThreads, threadsMarkdown } from "./threads";

const BASE_REF = required("BASE_REF");
const VERDICT = "/tmp/review-verdict.md";

const git = (...args: string[]): string =>
  execFileSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
const readJson = (file: string): unknown =>
  JSON.parse(fs.readFileSync(file, "utf8"));

const start = git("rev-parse", "HEAD").trim();
const threads = reviewThreads(readJson("/tmp/review-thread-comments.json"), {
  reviewer: fs.readFileSync("/tmp/review-reviewer.txt", "utf8").trim(),
  author: required("PR_AUTHOR"),
  writers: z.array(z.string()).parse(readJson("/tmp/review-writers.json")),
});
fs.writeFileSync("/tmp/review-threads.md", threadsMarkdown(threads));

const result = await runWithExtraction({
  name: "review",
  agent: claudeAgent(),
  sandbox: noSandbox(),
  logging: { type: "stdout" },
  promptFile: path.join(import.meta.dirname, "prompt.md"),
  promptArgs: {
    PR_NUMBER: required("PR_NUMBER"),
    BRANCH: required("BRANCH"),
    BASE_REF,
  },
  output: sandcastle.Output.object({ tag: "comments", schema: reviewSchema }),
  extractionPrompt: extractionPrompt("comments", reviewSchema),
});

const hunks = diffLines(git("diff", `origin/${BASE_REF}...HEAD`));
const { comments: found, applied }: z.infer<typeof reviewSchema> =
  result.output;
const inDiff = ({ path: file, line }: { path: string; line: number }) =>
  hunks.get(file)?.has(line) ?? false;
const posted = found.filter(inDiff);
const dropped = found.filter((comment) => !inDiff(comment));
for (const { path: file, line } of dropped) {
  console.error(
    `${file}:${line} is not in the diff: the finding goes in the verdict.`
  );
}

const written = fs.existsSync(VERDICT)
  ? fs.readFileSync(VERDICT, "utf8")
  : undefined;
const verdict =
  written ??
  "The review run produced no verdict. See the logs. Re-add `agent:review` to retry.\n";
fs.writeFileSync(VERDICT, addLeftFindings(verdict, posted, dropped));
writeJson(
  "review-status.json",
  reviewStatus(written, posted.length + dropped.length)
);

const runCommits = git("rev-list", `${start}..HEAD`)
  .split("\n")
  .filter(Boolean);
const { replies, refused } = repliesToAnswers(applied, threads, runCommits);
for (const reason of refused) console.error(`No reply: ${reason}`);
writeJson("review-replies.json", replies);

writeJson("review-comments.json", {
  commit_id: git("rev-parse", "HEAD").trim(),
  event: "COMMENT",
  body: "The findings this review left for you, on their lines. The verdict is in its own comment.",
  comments: posted.map(({ path: file, line, body }) => ({
    path: file,
    line,
    body,
    side: "RIGHT",
  })),
});
