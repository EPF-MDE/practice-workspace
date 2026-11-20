# The Engine holds no comment, and a ratchet counts the ones left

An agent writes most of the Engine's code, and reads the comments around it as truth. A comment that only says what the code shows costs tokens on every read. A stale one misleads. One that excuses a shortcut lets the agent copy the shortcut elsewhere. One that records a decision hides it where nobody searches, and it goes stale the moment someone changes the code without reading it. In November 2026 a pass sorted every comment in the Engine into these four kinds and deleted 922 of them: the decisions worth an ADR went into ADRs 0002 to 0014, a few into the glossary, and the excuses into issues.

**So the Engine's code holds no comment. A name says what the code does, a test says how it behaves, an ADR says why, and an issue says what is left to fix.** CODING_STANDARDS.md's "A decision lives in an ADR, not a comment" is the rule the review applies; this ADR is the one `npm run check` enforces.

- A comment is any `//`, `/* */` or JSX `{/* */}` comment in TS and JS, any `#` comment or docstring in Python, and any `#` line in a shell script but its shebang. A tool's directive is not a comment: `@ts-expect-error`, `@ts-check`, a `@type` annotation, `oxlint-disable`, `biome-ignore`, `noqa`, `type: ignore` and the like.
- `lint-rules/comments.js` (the oxlint rule `comments/no-comments`) checks TS and JS. `scripts/check-comments.py` checks Python and shell, because ruff has no such rule. `npm run check` runs both, and so does the pre-commit hook on the files it is given.
- `lint-rules/comments-baseline.json` is the ratchet: how many comments each file may still hold, 0 for a file it does not list. More fails the check, and so does fewer, until the entry is lowered: the count only goes down. An entry for a file that no longer exists fails too.
- Configuration files keep their comments: the workflows, TOML, the Dockerfile and `tsconfig.json`. Neither check reads them.
- The generated client in `frontend/src/client/` is out of the ban: it is written by `npm --prefix frontend run generate-client`, and its descriptions come from the back end's routes and models.
- The `/delete-comment` skill repeats the pass on any part of the Engine that grows comments again.

## Considered options

- **Ban comments outright, in one change.** Rejected: a comment that a tool reads at runtime, such as the docstring argparse prints as `backend/app/repository_reading/batch.py`'s `--help`, cannot simply go, and a ban leaves no room for one.
- **Leave it to the review.** Rejected: CODING_STANDARDS.md already had the rule, and 944 comments had piled up behind it.
