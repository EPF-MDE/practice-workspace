# An issue waiting on another ticket is blocked by it on GitHub, and goes back to explore when it closes

`agent-explore.yml` used to turn every tag but `easy-call` into `needs-a-human`. On 26 November 2026, 13 issues carried that label. Explore had tagged 10 of them `blocked`, and their blockers had all merged. Still, nothing put them back in the queue, and none needed a person. **So an issue explore tags `blocked` names the open issues it waits on, in the plan's `blocked_by`. Apply marks them as its blockers with GitHub's own "blocked by" relation and labels the issue `agent:blocked-by-ticket`. When one of them closes, the `unblock` job puts `agent:explore` back on each issue it blocked that has no open blocker left. `needs-a-human` is kept for a decision, and the plan states it in `decision`: one question with its options, which apply posts last in the comment.**

- **A blocker is an open issue.** The plan check refuses one that is not open when the batch is listed: a closed one would send the issue straight back to explore, to be found blocked again. For a pull request, explore names the issue the pull request closes.
- **The label goes on before apply reads the blockers.** A blocker that closes after that point finds the label, and `unblock` releases the issue. If every blocker closed before then, apply releases the issue itself.
- **`unblock` only moves issues labelled `agent:blocked-by-ticket`.** A relation that someone drew by hand on an issue the factory does not hold starts nothing.
- **An issue that is explored again loses `agent:blocked-by-ticket`** when its batch is listed, so an old blocker that closes cannot send it back once it is being implemented.
- **A name or a two-way choice that the glossary, an ADR or CODING_STANDARDS.md settles is no decision for a person.** Explore makes the choice and gives its reasoning in the comment, and the implementer carries that reasoning into its pull request, where the review can turn it back.

## Considered options

- **Keep `blocked` as `needs-a-human`.** This is what the workflow did before. A person had to notice that a blocker had merged and then add `agent:explore` again.
- **Name the blockers only in the comment, and re-read every blocked issue at night.** Rejected: a scheduled run reads every blocked issue whether anything closed or not, and an issue would wait up to a day after its blocker closed. GitHub's relation shows on both issues, and closing a blocker is the event that matters.
