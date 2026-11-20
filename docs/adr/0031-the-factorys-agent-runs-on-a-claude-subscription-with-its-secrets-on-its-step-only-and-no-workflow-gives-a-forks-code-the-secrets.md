# The Software Factory's agent runs on a Claude subscription, with its secrets on its step only, and no workflow gives a fork's code the secrets

Every Software Factory workflow runs one agent, `claudeAgent` in `.sandcastle/agent-workflows/shared/common.ts`. Its workflows hold secrets the agent needs (`CLAUDE_CODE_OAUTH_TOKEN`, and `POSTHOG_API_KEY` for the factory's own PostHog), and the Engine is public, so anyone can open a pull request from a fork. **So the agent authenticates with a Claude subscription, through `CLAUDE_CODE_OAUTH_TOKEN`, and runs with its permission checks skipped, as Sandcastle runs every agent, so it can use any tool. What keeps it in bounds is the workflow around it, which `npm run check` guards: it refuses a workflow that hands an agent-only secret to a step that does not run the agent, or hands any step every secret at once (`scripts/check-agent-secrets.js`), and it refuses any workflow triggered by `pull_request_target` or `workflow_run` (`scripts/check-workflow-triggers.js`).**

- **The agent's step is the one whose `run` calls a script in `.sandcastle/agent-workflows/`.** An agent-only secret set in a workflow's or a job's `env`, or in any other step's, fails the check; so does `toJSON(secrets)` anywhere.
- **`pull_request_target` and `workflow_run` run in the base repository's context**, with its secrets and a write token, even for a fork's code. On `pull_request`, GitHub gives a fork's pull request neither: it runs with a read-only token and no secret.
- **These come from the factory's spec**, issue #503 of the repository the Engine was first built in (story 36 and "Added on top: PostHog"), and from issue #509 of that same repository.

## Considered options

- **Bill the API with `ANTHROPIC_API_KEY`.** Possible at any time: pass `ANTHROPIC_API_KEY` in `claudeAgent` and in the workflow's env in place of `CLAUDE_CODE_OAUTH_TOKEN`.
- **`permissionMode: "auto"`, AI-mediated approvals.** Claude Code accepts it, and Sandcastle then passes it in place of skipping the checks, but only Claude offers it; other agents do not.
