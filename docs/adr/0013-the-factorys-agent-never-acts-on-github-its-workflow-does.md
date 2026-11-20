# The Software Factory's agent never acts on GitHub: its workflow does

Each run of the Software Factory is a GitHub Actions workflow that runs one agent script in `.sandcastle/agent-workflows/`. What the run does on GitHub (pushing, opening a pull request, creating issues, commenting, labelling) could be done by the agent itself or by the workflow steps around it. **So the agent never acts on GitHub: it edits and commits in the checkout, or hands back a structured answer, and the workflow steps after it do every push, pull request, issue, comment and label.** What reaches GitHub is then in a workflow step, where the Instructor can read it.

- **The agent holds no GitHub token.** The workflow gives the factory's token only to the steps that call GitHub, and checks the code out with `persist-credentials: false`. That is tidiness, not a wall, since the agent shares the machine with those steps: the defence is who can reach the agent (ADR-0014).
- **The agent commits through the pre-commit hook**, so it has to fix whatever the hook rejects before the workflow pushes.
- **A structured answer is a contract with its workflow.** Each schema the agent answers in (`explore/plan-schema.ts`, `implement-spec/decomposition-schema.ts`, `review/review-schema.ts`) is what a workflow acts on: changing it means changing that workflow in the same change.
