# A spec's tickets wait on each other through GitHub's `blocked by` relation

`agent-implement-spec.yml` decomposes a spec into a queue of tickets and builds them one at a time. It used to write what a ticket waits on as a `Depends on: 7` line in the ticket's body, which only its own survey read. GitHub showed no relation, so on 26 November 2026 three tickets of one spec sat `agent:queued` behind another's unmerged pull request with nothing on GitHub saying why, and `7`, a position, read like issue #7. **So what a ticket waits on is GitHub's own `blocked by` relation, and only that: the decompose loop creates each ticket as a sub-issue of the spec, blocked by the tickets of the positions it depends on, and the survey reads `blockedBy`. The body keeps `Position:`, which orders the queue, and has no `Depends on:` line.**

- **Tickets are created in position order**, and a ticket depends only on lower positions, so each blocker exists when the ticket that waits on it is created. A ticket that depends on a later position stops the loop with an error before it is created.
- **A person edits the relation on GitHub**, and the next survey reads it. Nothing else records it, so there is no second copy to disagree with.
- **The frontier is the lowest open position, neither parked nor awaiting its own pull request's merge, whose blockers are all closed.** A blocker outside the queue counts by its own state.
- **When the chain stops, the notice names each open ticket and what it waits on**: its own pull request, or its open blockers, each with its pull request, or `(parked)` when it carries `agent:blocked`.

## Considered options

- **Keep `Depends on:` in the body and also add the relations.** Rejected: two records of one thing, which a person editing one of them makes disagree.
- **Write `Depends on:` with issue numbers instead of positions.** Rejected: still invisible to GitHub's own views of the spec and its tickets.
