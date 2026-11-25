# A `pull_request_target` workflow runs only `gh`, on a same-repository pull request

GitHub runs no `pull_request` workflow on a pull request that conflicts with its base ([GitHub's docs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request): "Workflows will not run on `pull_request` activity if the pull request has a merge conflict"). So a factory label on such a pull request started nothing, and nothing said so: `agent:review` on #72, and on #81 for a day, did nothing until the Instructor asked. The same page says `pull_request_target` "will run even if the pull request has a merge conflict", but it runs in the base repository's context, with its secrets, whoever opened the pull request, which ADR-0014 forbade. **So a workflow may run on `pull_request_target` only if no code of the pull request can run in it: it checks out nothing, uses no action, calls no `git`, interpolates no `${{ }}` expression in a script, and every job skips a fork's pull request. `scripts/check-workflow-triggers.js` refuses one that breaks any of these. `workflow_run` stays forbidden.** This amends ADR-0014, which forbade `pull_request_target` outright.

- **`agent-answer-labels.yml` is the one such workflow.** It answers `agent:rebase` and `agent:review` with `gh` alone: it comments, and starts `agent-rebase.yml` through `workflow_dispatch`. The rebase, which checks out and runs the pull request's code, keeps running on `workflow_dispatch`, `push` and `schedule` only, and its survey leaves forks out.
- **No expression in a script**, because a pull request's title, body or branch name interpolated into `run` is a script injection. The workflow reads the pull request's number and the label's name through `env`.
- **A fork's pull request is skipped** even though only a collaborator can label one: the label is no reason to give a stranger's pull request a step holding the factory's token.

## Considered options

- **Wait for the nightly rebase.** It is what `agent-rebase.yml` did: the label waited up to a day, with no comment.
- **A scheduled survey of the labels on conflicting pull requests.** GitHub's schedules ran hours late on 23 and 24 November, so it answers no faster than the night.
