import { z } from "zod/v4";

export const APPLIED_MARKER = "<!-- agent-review: applied -->";

const reviewCommentSchema = z.object({
  id: z.number(),
  in_reply_to_id: z.number().nullish(),
  user: z.object({ login: z.string(), type: z.string() }).nullable(),
  path: z.string(),
  line: z.number().nullish(),
  original_line: z.number().nullish(),
  body: z.string(),
  created_at: z.string(),
});

type ReviewComment = z.infer<typeof reviewCommentSchema>;

export type ThreadState = "open" | "answered" | "applied";

export type Answer = { by: string; at: string; body: string };

export type Thread = {
  id: number;
  path: string;
  line: number | null;
  outdated: boolean;
  finding: string;
  answers: Answer[];
  state: ThreadState;
};

export type People = { author: string; writers: string[] };

const canAnswer =
  ({ author, writers }: People) =>
  ({ user, body }: ReviewComment): boolean =>
    user !== null &&
    user.type !== "Bot" &&
    (user.login === author || writers.includes(user.login)) &&
    !body.includes(APPLIED_MARKER);

const stateOf = (answers: ReviewComment[], applied: ReviewComment[]) => {
  const lastAnswer = answers.at(-1);
  if (!lastAnswer) return "open";
  const lastApplied = applied.at(-1);
  return lastApplied && lastApplied.id > lastAnswer.id ? "applied" : "answered";
};

export const reviewThreads = (comments: unknown, people: People): Thread[] => {
  const all = [...z.array(reviewCommentSchema).parse(comments)].sort(
    (a, b) => a.id - b.id
  );
  const repliesTo = (root: ReviewComment) =>
    all.filter(({ in_reply_to_id }) => in_reply_to_id === root.id);

  return all
    .filter(({ in_reply_to_id }) => in_reply_to_id == null)
    .map((root) => {
      const replies = repliesTo(root);
      const answers = replies.filter(canAnswer(people));
      const applied = replies.filter(({ body }) =>
        body.includes(APPLIED_MARKER)
      );
      return {
        id: root.id,
        path: root.path,
        line: root.line ?? root.original_line ?? null,
        outdated: root.line == null,
        finding: root.body,
        answers: answers.map(({ user, created_at, body }) => ({
          by: user?.login ?? "",
          at: created_at,
          body,
        })),
        state: stateOf(answers, applied),
      };
    });
};

const quote = (text: string): string =>
  text
    .trim()
    .split("\n")
    .map((line) => (line ? `> ${line}` : ">"))
    .join("\n");

const threadMarkdown = (thread: Thread): string =>
  [
    `## Thread ${thread.id}: ${thread.state}`,
    "",
    `\`${thread.path}:${thread.line ?? "?"}\`${thread.outdated ? ", on a line the branch has since changed" : ""}`,
    "",
    "The finding:",
    "",
    quote(thread.finding),
    ...thread.answers.flatMap(({ by, at, body }) => [
      "",
      `Answered by ${by}, ${at}:`,
      "",
      quote(body),
    ]),
  ].join("\n");

export const threadsMarkdown = (threads: Thread[]): string =>
  threads.length === 0
    ? "This pull request has no earlier review threads.\n"
    : `${threads.map(threadMarkdown).join("\n\n")}\n`;

export type Applied = {
  thread: number;
  commit: string | null;
  summary: string;
};

export type Reply = { thread: number; body: string };

export const repliesToAnswers = (
  applied: Applied[],
  threads: Thread[],
  runCommits: string[]
): { replies: Reply[]; refused: string[] } => {
  const answered = new Set(
    threads.filter(({ state }) => state === "answered").map(({ id }) => id)
  );
  const replies: Reply[] = [];
  const refused: string[] = [];

  for (const { thread, commit, summary } of applied) {
    if (!answered.has(thread)) {
      refused.push(`Thread ${thread} has no answer left to apply.`);
      continue;
    }
    const full =
      commit === null
        ? null
        : runCommits.find(
            (sha) => commit.length >= 7 && sha.startsWith(commit)
          );
    if (full === undefined) {
      refused.push(
        `Thread ${thread}: ${commit} is not a commit of this review.`
      );
      continue;
    }
    answered.delete(thread);
    const head = full
      ? `Applied in ${full}: ${summary}`
      : `Read, and nothing to change: ${summary}`;
    replies.push({ thread, body: `${head}\n\n${APPLIED_MARKER}` });
  }

  return { replies, refused };
};
