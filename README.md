# Practice workspace

A space where each Student of a course practises its Competencies on their
own, one Path at a time: they read the material, answer, redraw its systems,
and see the Instructor's answer only once their own is stored. They leave
with a Self-assessment and an Evidence Plan, and later sit their Eval on the
same kind of Path.

It is one public engine. Each course that uses it keeps its material private
and runs its own instance, on a released version of the engine
([ADR-0001](./docs/adr/0001-one-public-engine-and-one-instance-per-course.md)).
It is written for the courses of EPF's MDE programme, and holds none of them.

**Status:** the repository and its guardrail. The engine arrives next, with a
fictional demo course you can run locally.

## Working on it

Read [AGENTS.md](./AGENTS.md). In short: `npm run check` runs everything, and
a pre-commit hook runs its fast part. Its words are in
[GLOSSARY.md](./GLOSSARY.md).

The guardrail is set up as the
[Software Factories cohort](https://github.com/ai-hero-dev/cohort-005-project)
sets it up, with CI on every pull request on top.

## Licence

[MIT](./LICENSE).
