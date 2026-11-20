import { readFileSync } from "node:fs";
import { relative } from "node:path";

export const BASELINE = "lint-rules/comments-baseline.json";

const DIRECTIVE =
  /^\s*(@ts-expect-error|@ts-ignore|@ts-nocheck|@ts-check|\*\s*@type\s*\{|oxlint-disable|eslint-disable|biome-ignore|@vite-ignore|#__PURE__|@__PURE__)|^\/\s*<reference /;

const readBaseline = (root) => {
  try {
    return JSON.parse(readFileSync(`${root}/${BASELINE}`, "utf8"));
  } catch {
    return {};
  }
};

const noComments = {
  meta: {
    type: "suggestion",
    messages: {
      over: "{{count}} comments, and {{path}} may hold {{allowed}}. Delete the comment: a name says what, an ADR in docs/adr/ says why. See CODING_STANDARDS.md, A decision lives in an ADR, not a comment.",
      under:
        "{{count}} comments, fewer than the {{allowed}} {{baseline}} allows for {{path}}: lower its entry to {{count}}, or remove it at 0.",
    },
  },
  create(context) {
    const root = context.cwd ?? process.cwd();
    const path = relative(root, context.filename);
    const allowed = readBaseline(root)[path] ?? 0;
    return {
      "Program:exit"(node) {
        const comments = context.sourceCode
          .getAllComments()
          .filter((comment) => !DIRECTIVE.test(comment.value));
        const count = comments.length;
        const data = { count, allowed, path, baseline: BASELINE };
        if (count > allowed) {
          context.report({ node: comments[allowed], messageId: "over", data });
        } else if (count < allowed) {
          context.report({ node, messageId: "under", data });
        }
      },
    };
  },
};

export default {
  meta: { name: "comments" },
  rules: { "no-comments": noComments },
};
