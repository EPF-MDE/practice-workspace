# One check defines green, the pre-commit hook runs its fast part, and no file is over 5000 tokens

An implementing agent, the review run, CI and the Instructor each need to know when a change is green, and each could run its own set of commands. Agents implement and review the Engine, and a file too big to read whole is one they edit blind. **So `npm run check` (`scripts/check.sh`) is the one definition of green, everything in one command; the pre-commit hook (`scripts/pre-commit.sh`) runs its fast part, every job in parallel, in a few seconds; and both refuse any file over 5000 tokens, through `scripts/check-file-tokens.js`.**

- **Tests stay in `npm run check`**, out of the hook.
- **`npm run check` runs in parts.** Its parts are `repository`, `backend` and `frontend`; `npm run check -- <part> ...` runs only those, and with no part, every part runs.
- **The commands both run are defined once**, in `scripts/check-steps.sh`, which both source rather than run: `check.sh` runs them in sequence, `pre-commit.sh` in parallel. Each runs from the repository's root.
- **lint-staged runs with `--no-stash`.** Its checks never write, and stashing would change the working tree under the checks running beside it.
- **The file limit is estimated as bytes / 4**, which is close enough for code. `npm run check` applies it to every tracked file, and the hook, through lint-staged, to every staged one.
- **Some files are exempt from the limit**: generated files nobody edits by hand (`package-lock.json`, `uv.lock`, the front end's generated client and route tree), and workflow files, which GitHub reads as one file each and which cannot be split.
- **Only regular files are read.** git lists a symlink as one path, such as `.agents/skills`, a link to `.claude/skills`; its target is checked on its own path, so `isRegularFile` uses `lstatSync` and skips the link.
- **Binary files are skipped.**
