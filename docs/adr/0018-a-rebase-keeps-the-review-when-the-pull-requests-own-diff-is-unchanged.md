# A rebase keeps the review when the pull request's own diff is unchanged

Every merge onto `main` leaves the other open pull requests behind it, so `agent-rebase.yml` rebases them on every push to `main` as well as at night. Asking for `agent:review` after each of those rebases made #81 to #84 each go through two or three review cycles on 24 November, though most rebases changed nothing the review had read. **So a rebase keeps the pull request's review when nothing the review read changed: the script rebased it with no agent, `npm run check` passes, and the pull request's own diff is the same as before, compared with `git patch-id --stable`. Any other push asks for `agent:review`.**

- **The diff the review read** is the pull request's head against its merge-base with the base before the rebase; the diff it would read now is the new head against the new base. `git patch-id --stable` leaves out line numbers, so a base that only moved the pull request's lines keeps the same id, and one that changed them, or the lines of context around them, does not.
- **An agent's resolution always asks for a review**: it is code nobody has read.
- **An `agent:review` left waiting** while the pull request conflicted also asks for one, since a person asked for it, and the label goes on once GitHub calls the pull request mergeable.
- **The decision is one step**, "Decide whether the review stands", which writes `review` (`keep` or `request`) and `because`; the report and the hand-off only follow it.
- **The `agent-review` commit status of the old head goes on the new head** when the review stands, so a required `agent-review` check does not wait for a review nobody needs. `FACTORY_PAT` needs Commit statuses: write for it; without it the run warns and the review still stands.
- **`agent:review` is added after `agent:in-progress` comes off**, so the rebase never removes the label of the review it started.

## Considered options

- **Ask for a review after every push.** It is what the rebase did: a review cycle per merge, each reading the whole pull request again.
- **Keep the review whenever the script rebased without conflict and `npm run check` passes.** Rejected: a base that changed the lines in or beside the pull request's own changes makes them read differently, and the review read them in their old context.
