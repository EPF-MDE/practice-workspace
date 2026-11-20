// The agent-secrets check, run as `npm run check` runs it: on workflow files.

import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-agent-secrets.js");

const checkWorkflow = (workflow) => {
  const file = join(
    mkdtempSync(join(tmpdir(), "check-agent-secrets-")),
    "agent.yml"
  );
  writeFileSync(file, workflow);
  return spawnSync("node", [script, file], { encoding: "utf8" });
};

const agentStep = `
      - name: Build the ticket
        env:
          CLAUDE_CODE_OAUTH_TOKEN: \${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          POSTHOG_API_KEY: \${{ secrets.POSTHOG_API_KEY }}
        run: npx tsx .sandcastle/agent-workflows/implement/implement.ts`;

const workflowWith = ({ jobEnv = "", steps = "" } = {}) => `
# POSTHOG_API_KEY: a comment may name it.
on:
  issues:
    types: [labeled]
jobs:
  implement:
    runs-on: ubuntu-latest
${jobEnv}
    steps:
${agentStep}
${steps}`;

describe("check-agent-secrets on POSTHOG_API_KEY", () => {
  it("passes POSTHOG_API_KEY on the step that runs the agent", () => {
    const result = checkWorkflow(workflowWith());

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses POSTHOG_API_KEY on any other step", () => {
    const result = checkWorkflow(
      workflowWith({
        steps: `
      - name: Send the sessions
        if: always()
        env:
          POSTHOG_API_KEY: \${{ secrets.POSTHOG_API_KEY }}
        run: python3 ingest.py`,
      })
    );

    expect(result.stderr).toContain(
      `job "implement", step "Send the sessions"`
    );
    expect(result.status).toBe(1);
  });

  it("refuses POSTHOG_API_KEY in a job's env, where every step reads it", () => {
    const result = checkWorkflow(
      workflowWith({
        jobEnv: `    env:
      POSTHOG_API_KEY: \${{ secrets.POSTHOG_API_KEY }}`,
      })
    );

    expect(result.stderr).toContain(`job "implement", its env`);
    expect(result.status).toBe(1);
  });

  it("refuses POSTHOG_API_KEY in the workflow's env", () => {
    const result = checkWorkflow(
      `env:\n  POSTHOG_API_KEY: \${{ secrets.POSTHOG_API_KEY }}\n${workflowWith()}`
    );

    expect(result.stderr).toContain("the workflow's env");
    expect(result.status).toBe(1);
  });
});

describe("check-agent-secrets on the agent's token and every secret", () => {
  it("refuses CLAUDE_CODE_OAUTH_TOKEN on any other step", () => {
    const result = checkWorkflow(
      workflowWith({
        steps: `
      - name: Summarise the run
        env:
          CLAUDE_CODE_OAUTH_TOKEN: \${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: claude -p "Summarise"`,
      })
    );

    expect(result.stderr).toContain(
      `CLAUDE_CODE_OAUTH_TOKEN in job "implement", step "Summarise the run"`
    );
    expect(result.status).toBe(1);
  });

  it("passes a step that only names a secret in its name or its run", () => {
    const result = checkWorkflow(
      workflowWith({
        steps: `
      - name: Say POSTHOG_API_KEY is set
        run: echo "POSTHOG_API_KEY and CLAUDE_CODE_OAUTH_TOKEN stay on the agent's step"`,
      })
    );

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses toJSON(secrets) anywhere, the agent's step included", () => {
    const result = checkWorkflow(
      workflowWith({
        steps: `
      - name: Dump everything
        env:
          ALL: \${{ toJson( secrets ) }}
        run: npx tsx .sandcastle/agent-workflows/implement/implement.ts`,
      })
    );

    expect(result.stderr).toContain(
      `toJSON(secrets) in job "implement", step "Dump everything"`
    );
    expect(result.status).toBe(1);
  });
});
