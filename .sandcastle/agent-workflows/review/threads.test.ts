import { describe, expect, it } from "vitest";
import {
  APPLIED_MARKER,
  repliesToAnswers,
  reviewThreads,
  type Thread,
  threadsMarkdown,
} from "./threads";

const people = { author: "author", writers: ["instructor"] };

let nextId = 100;

const comment = (
  overrides: {
    id?: number;
    in_reply_to_id?: number;
    login?: string;
    type?: string;
    body?: string;
    line?: number | null;
  } = {}
) => {
  const id = overrides.id ?? nextId++;
  return {
    id,
    ...(overrides.in_reply_to_id === undefined
      ? {}
      : { in_reply_to_id: overrides.in_reply_to_id }),
    user: {
      login: overrides.login ?? "instructor",
      type: overrides.type ?? "User",
    },
    path: "backend/app/content/parse.py",
    line: overrides.line === undefined ? 93 : overrides.line,
    original_line: 87,
    body: overrides.body ?? "A finding.",
    created_at: `2026-11-23T17:${String(id % 60).padStart(2, "0")}:00Z`,
    commit_id: "0123456789abcdef0123456789abcdef01234567",
    author_association: "MEMBER",
  };
};

const finding = (id: number, body = "Refuse or accept the old field?") =>
  comment({ id, body });

const reply = (to: number, body: string, login = "instructor") =>
  comment({ in_reply_to_id: to, body, login });

describe("reviewThreads", () => {
  it("leaves a finding nobody answered open", () => {
    const [thread] = reviewThreads([finding(1)], people);

    expect(thread).toMatchObject({
      id: 1,
      path: "backend/app/content/parse.py",
      line: 93,
      outdated: false,
      finding: "Refuse or accept the old field?",
      answers: [],
      state: "open",
    });
  });

  it("gives each finding the answers replying to it", () => {
    const threads = reviewThreads(
      [
        finding(1),
        finding(2),
        reply(1, "Keep refusing"),
        reply(2, "Accept it"),
      ],
      people
    );

    expect(
      threads.map(({ id, state, answers }) => [
        id,
        state,
        answers.map(({ body }) => body),
      ])
    ).toEqual([
      [1, "answered", ["Keep refusing"]],
      [2, "answered", ["Accept it"]],
    ]);
  });

  it("takes answers from the pull request's author and from writers only", () => {
    const [thread] = reviewThreads(
      [
        finding(1),
        reply(1, "From the author", "author"),
        reply(1, "From a passer-by", "stranger"),
        reply(1, "From the Instructor", "instructor"),
      ],
      people
    );

    expect(thread?.answers.map(({ by }) => by)).toEqual([
      "author",
      "instructor",
    ]);
  });
});

describe("reviewThreads, on who answered", () => {
  it("leaves out a bot's reply, even from a writer's name", () => {
    const [thread] = reviewThreads(
      [
        finding(1),
        comment({ in_reply_to_id: 1, body: "Looks good", type: "Bot" }),
      ],
      people
    );

    expect(thread?.state).toBe("open");
  });
});

describe("reviewThreads, on what was applied", () => {
  it("reads the workflow's reply after the last answer as applied", () => {
    const [thread] = reviewThreads(
      [
        finding(1),
        reply(1, "Keep refusing"),
        reply(1, `Applied in abc.\n\n${APPLIED_MARKER}`),
      ],
      people
    );

    expect(thread?.state).toBe("applied");
    expect(thread?.answers.map(({ body }) => body)).toEqual(["Keep refusing"]);
  });

  it("reads an answer given after the workflow's reply as answered again", () => {
    const [thread] = reviewThreads(
      [
        finding(1),
        reply(1, "Keep refusing"),
        reply(1, `Applied in abc.\n\n${APPLIED_MARKER}`),
        reply(1, "Actually, say why in the error"),
      ],
      people
    );

    expect(thread?.state).toBe("answered");
  });

  it("gives an outdated finding its original line", () => {
    const [thread] = reviewThreads([comment({ id: 1, line: null })], people);

    expect(thread).toMatchObject({ line: 87, outdated: true });
  });

  it("refuses what is not a list of review comments", () => {
    expect(() => reviewThreads([{ id: "one" }], people)).toThrow();
  });
});

describe("threadsMarkdown", () => {
  it("says so when there is no earlier thread", () => {
    expect(threadsMarkdown([])).toBe(
      "This pull request has no earlier review threads.\n"
    );
  });

  it("quotes each finding and each answer under its thread", () => {
    const markdown = threadsMarkdown(
      reviewThreads(
        [finding(1, "Refuse?\n\nOr accept?"), reply(1, "Keep refusing")],
        people
      )
    );

    expect(markdown).toContain("## Thread 1: answered");
    expect(markdown).toContain("> Refuse?\n>\n> Or accept?");
    expect(markdown).toContain("Answered by instructor");
    expect(markdown).toContain("> Keep refusing");
  });
});

const sha = "abcdef0123456789abcdef0123456789abcdef01";
const threads: Thread[] = reviewThreads(
  [finding(1), reply(1, "Keep refusing"), finding(2)],
  people
);

describe("repliesToAnswers", () => {
  it("replies on an answered thread with the full commit that applied it", () => {
    const { replies, refused } = repliesToAnswers(
      [
        {
          thread: 1,
          commit: "abcdef0",
          summary: "Kept the refusal and tested it.",
        },
      ],
      threads,
      [sha]
    );

    expect(refused).toEqual([]);
    expect(replies).toEqual([
      {
        thread: 1,
        body: `Applied in ${sha}: Kept the refusal and tested it.\n\n${APPLIED_MARKER}`,
      },
    ]);
  });

  it("replies with no commit when the answer changes nothing", () => {
    const { replies } = repliesToAnswers(
      [{ thread: 1, commit: null, summary: "The code already refuses it." }],
      threads,
      []
    );

    expect(replies[0]?.body).toBe(
      `Read, and nothing to change: The code already refuses it.\n\n${APPLIED_MARKER}`
    );
  });
});

describe("repliesToAnswers, refusing", () => {
  it("refuses a commit this review did not make", () => {
    const { replies, refused } = repliesToAnswers(
      [{ thread: 1, commit: "1234567", summary: "Done." }],
      threads,
      [sha]
    );

    expect(replies).toEqual([]);
    expect(refused).toHaveLength(1);
  });

  it("refuses a thread with no answer to apply", () => {
    const { replies } = repliesToAnswers(
      [{ thread: 2, commit: null, summary: "Done." }],
      threads,
      [sha]
    );

    expect(replies).toEqual([]);
  });

  it("replies once per thread", () => {
    const { replies } = repliesToAnswers(
      [
        { thread: 1, commit: null, summary: "Done." },
        { thread: 1, commit: null, summary: "Done again." },
      ],
      threads,
      []
    );

    expect(replies).toHaveLength(1);
  });
});
