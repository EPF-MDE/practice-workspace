# Practice workspace

A space where each Student of a course practises its Competencies on their own, one Path at a time: they read the material, answer, redraw its systems, and see the Instructor's answer only once their own is stored. They leave with a Self-assessment and an Evidence Plan, and later sit their Eval on the same kind of Path.

It is one public engine. Each course that uses it keeps its material private and runs its own instance, on a released version of the engine ([ADR-0001](./docs/adr/0001-one-public-engine-and-one-instance-per-course.md)). It is written for the courses of EPF's MDE programme, and holds none of them.

**Status:** the engine, imported from the course it was built for, running on a fictional Demo course. Some of that course's values are still in the code (its two Groups, its three Competencies, its dates and one slide); they move to a Course folder's settings next.

## Run the Demo course

You need Node 24 and [uv](https://docs.astral.sh/uv/).

```sh
npm install && npm --prefix frontend install && (cd backend && uv sync)
npm run demo
```

Then open <http://localhost:8000/auth/login?github_id=1001> to sign in as a fictional Student (any id in [`demo-course/roster.csv`](./demo-course/roster.csv) works). Sign-in is faked and nothing is kept once the server stops.

The engine reads a course at start from the folder `WORKSPACE_CONTENT_DIR` names: one Markdown file per Competency (`c1.md`…) and its drawings. [`demo-course/`](./demo-course/) is one; the content format is described in [docs/content-format.md](./docs/content-format.md).

## Working on it

Read [CLAUDE.md](./CLAUDE.md). In short: `npm run check` runs everything, and a pre-commit hook runs its fast part. Its words are in [GLOSSARY.md](./GLOSSARY.md).

## Credits

The guardrail and the software factory come from the [Software Factories for Real Engineers](https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m) cohort's repository, [ai-hero-dev/cohort-005-project@4339a30](https://github.com/ai-hero-dev/cohort-005-project/tree/4339a3095c5d85e4fb2b3b60ff6c1e6d18147180), with CI on every pull request on top. From it:

- copied: the `code-review`, `pr` and `retro` skills in `.claude/skills/`, the `.sandcastle/` folder, the `agent-implement`, `agent-review`, `agent-explore` and `agent-implement-spec` workflows, `scripts/check-file-tokens.js` and `lint-rules/input.js` (with the glossary's words);
- adapted: `tsconfig.json`, `scripts/pre-commit.sh` (with the back end's jobs added) and the rules in [CODING_STANDARDS.md](./CODING_STANDARDS.md).

The `pr` skill's menu of visuals for its Summary section comes from [Dex Horthy](https://github.com/dexhorthy)'s [`show-me`](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md) skill (HumanLayer), copied almost word for word.

## Licence

[MIT](./LICENSE).
