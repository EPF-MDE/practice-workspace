# Practice workspace

A space where each Student of a course practises its Competencies on their own, one Path at a time: they read the material, answer, redraw its systems, and see the Instructor's answer only once their own is stored. They leave with a Self-assessment and an Evidence Plan, and later sit their Eval on the same kind of Path.

It is one public engine. Each course that uses it keeps its material private and runs its own instance, on a released version of the engine ([ADR-0001](./docs/adr/0001-one-public-engine-and-one-instance-per-course.md)). It is written for the courses of EPF's MDE programme, and holds none of them.

**Status:** the engine, imported from the course it was built for, running on a fictional Demo course. Everything that course owned, its Groups, their upstream repositories, its Close, its Reading Day and its slide, now comes from a Course folder. Every Course has the same three Competencies, C1, C2 and C3; its Course folder titles them and gives each Path its minutes.

## Run the Demo course

You need Node 24 and [uv](https://docs.astral.sh/uv/).

```sh
npm run setup
npm run demo
```

Then open <http://localhost:8000/auth/login?github_id=1001> to sign in as a fictional Student (any id in [`demo-course/roster.csv`](./demo-course/roster.csv) works). Sign-in is faked and nothing is kept once the server stops.

The engine reads a Course folder at start from the folder `WORKSPACE_COURSE_FOLDER` names: its settings in `course.toml` (the Course's `name`; each Group's name, the id of its Group block and its Upstream repository, if any; a `[competencies.C1]` table for each of C1, C2 and C3 with its `title` and `minutes`; its Self-assessment `levels`, in order, each with an `id` and a `label`, the last being the level that says a point is done; a `to-get-there` block names a level below it; and in `[calendar]` its Close and Reading Day with their `time_zone`; and in `read_when_none_declared` what is read when a Student declares no Evidence Project: `roster`, the one the Roster names, or `nothing`, so that the Evidence panel asks them to declare one), one Markdown file per Competency (`c1.md`, `c2.md`, `c3.md`), its drawings, and its images in `images/` (PNG, JPEG, GIF, WebP or SVG), which a Step shows with a plain Markdown image, `![what it shows](images/<file>)`, its path relative to the Course folder; the engine serves no other file of the folder (see [ADR-0019](./docs/adr/0019-the-engine-draws-no-slide-and-an-image-on-a-step-is-the-courses-material.md)). [`demo-course/`](./demo-course/) is one, and shows the format. The engine refuses to start on a Course folder it cannot serve, naming every problem it found; `uv run python -m app verify <course folder>`, run from `backend/`, loads the folder the same way and exits non-zero on any problem.

What belongs to the Instance stays in its environment, never in a Course folder: secrets, the GitHub Apps, PostHog, the public URL, the tldraw licence key, and the Store. With the GitHub Store (`WORKSPACE_STORE=github`), the engine refuses to start without `WORKSPACE_REPOSITORY` and `WORKSPACE_STORE_APP_SLUG`, and reading repositories through GitHub (`WORKSPACE_REPOSITORY_READING=github`) refuses without `WORKSPACE_REPOSITORY`: neither has a default.

## Working on it

Read [CLAUDE.md](./CLAUDE.md). In short: `npm run check` runs everything, and a pre-commit hook runs its fast part. Its words are in [GLOSSARY.md](./GLOSSARY.md).

## Credits

The guardrail and the software factory come from the [Software Factories for Real Engineers](https://www.aihero.dev/cohorts/software-factories-for-real-engineers-xdy1m) cohort's repository, [ai-hero-dev/cohort-005-project@4339a30](https://github.com/ai-hero-dev/cohort-005-project/tree/4339a3095c5d85e4fb2b3b60ff6c1e6d18147180), with CI on every pull request on top. From it:

- copied: the `code-review`, `pr` and `retro` skills in `.claude/skills/`, the `.sandcastle/` folder, the `agent-implement`, `agent-review`, `agent-explore` and `agent-implement-spec` workflows, `scripts/check-file-tokens.js` and `lint-rules/input.js` (with the glossary's words);
- adapted: `tsconfig.json`, `scripts/pre-commit.sh` (with the back end's jobs added) and the rules in [CODING_STANDARDS.md](./CODING_STANDARDS.md).

The `pr` skill's menu of visuals for its Summary section comes from [Dex Horthy](https://github.com/dexhorthy)'s [`show-me`](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md) skill (HumanLayer), copied almost word for word.

## Licence

[MIT](./LICENSE).
