---
name: delete-comment
description: "Sort the comments in a part of the Engine, delete them, and move what they knew into ADRs and issues."
disable-model-invocation: true
---

The user has asked you to **delete comments**. Every comment in the part of the Engine they name leaves the code. What a comment knew either survives somewhere better or was never worth keeping. `lint-rules/comments-baseline.json` is the **ratchet**: how many comments each file may still hold. It only goes down.

## Steps

1. **Scope.** Take the part the user names: a file, a folder or a Deep Module. If they name nothing, take the files with the highest counts in `lint-rules/comments-baseline.json`. The **comments** are every `#` comment and docstring in Python, every `//`, `/* */` and JSX `{/* */}` comment in TS/JS, and every `#` line in shell except the shebang. A tool's directive (`# noqa`, `# type: ignore`, `// @ts-expect-error`, `// oxlint-disable…`, `// biome-ignore…`) is not a comment: it stays. Done when you have a list of every comment in scope.

2. **Sort** each comment into exactly one category, checking it against the code and the tests:

   - **Tautology**: says what the code already shows.
   - **Stale**: describes code, behaviour or plans that no longer match.
   - **Excuse**: covers for a shortcut, a workaround, a TODO, a known limitation, or code that should read clearly without it (a poor name, a function waiting to be extracted).
   - **Decision Record**: a non-obvious _why_ that still holds, which a competent engineer reading only the code and tests would likely undo on purpose.

   Done when every comment on the list has a category.

3. **Act** on each one. Delete only comments: change no code, except `...` or `pass` where an empty body is left.

   - Tautology, Stale: delete it.
   - Excuse: delete it, and file one issue per fix with `gh issue create` (one issue covers every excuse that the same fix removes). The issue names the code by path and function, quotes the deleted comment, and says what the fix looks like.
   - Decision Record: delete it, and write the decision into an ADR in `docs/adr/`, in the style of ADR-0001, numbered after the highest one. Group the decisions about one Deep Module or one tool into one ADR. Where an ADR on the same subject exists, extend it rather than starting another.

   Issues and ADRs are public: write them in the glossary's words, with no course's material, Student or answer.

   Done when no comment in scope remains, apart from any you keep because deleting it is unsafe in this change, each with a reason you give the user.

4. **Ratchet.** Set each touched file's entry in `lint-rules/comments-baseline.json` to its new count, and remove entries that reach 0. The checks tell you each number: `npx oxlint -c .oxlintrc.json <files>` for TS/JS, and `uv run --project backend --frozen python scripts/check-comments.py <files>` for Python and shell. Done when both are silent on the files in scope.

5. **Verify.** If you deleted a FastAPI route's or a pydantic model's docstring, run `npm --prefix frontend run generate-client`: the docstring was the OpenAPI description. Then `npm run check`. Done when it passes.

6. **Report** the counts per category, the ADRs written or extended, the issues filed, and every comment kept with its reason. Name the ADRs and issues in the pull request.
