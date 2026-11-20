# Practice workspace

The public engine a course runs so that each Student practises its Competencies, one Path at a time. It holds no course: never commit a real course's material, a Student's name or data, or an answer to a Step. The Demo course is the only course here.

## Read first

- [GLOSSARY.md](./GLOSSARY.md): the engine's language. Use its words, and none on an _Avoid_ list, in code, tests, API and screen text.
- [docs/adr/](./docs/adr/): the decisions, starting with [ADR-0001](./docs/adr/0001-one-public-engine-and-one-instance-per-course.md), why the engine exists.
- [CODING_STANDARDS.md](./CODING_STANDARDS.md): the judgement rules the review checks. Every rule a machine can check is in `npm run check` instead.

## Layout

- `backend/`: one Python package, `app`, run with `uv`. Each subpackage of `app` is a Deep Module, reached from outside only through names not starting with `_`; `tach` enforces it, and import-linter forbids cycles between them.
- `frontend/`: the React front end, built and served by the back end. Each folder under `src/packages` is a Deep Module, reached from outside only through its root files; dependency-cruiser enforces it.
- `.sandcastle/`: the Software Factory's agent scripts, run with Sandcastle from the workflows in `.github/workflows/`. `npm run check` type-checks them.

## Verification

`npm run check` runs everything: file size, format, lint, types, boundaries, tests. Run it before you report a change as complete. CI runs it on every pull request, and `main` takes nothing that fails it.

Once per clone: `npm install`, `npm --prefix frontend install`, `(cd backend && uv sync)`. `npm install` installs the pre-commit hook.

The pre-commit hook runs the fast part of `check` in a few seconds, without the tests. It refuses any file over 5000 tokens, including one you only touched, so editing a large file means splitting it in the same change. Never skip it with `--no-verify`.

Never bypass the hook, and never edit it: `.husky/`, `scripts/pre-commit.sh`, `scripts/check-steps.sh` and `core.hooksPath` are the factory's brakes. Only the Instructor changes them. Leave `.github/` untouched too, unless the ticket explicitly asks for a change there: the Instructor's review before merge is then the guard.

## Issue tracker

Issues and specs are GitHub issues on EPF-MDE/practice-workspace, through the `gh` CLI. They are public: write them without any course's Students or answers.
