import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { SLOT_STEP } from "./slots";

type Step = { name?: string; run?: string; env?: Record<string, unknown> };
type Workflow = { jobs: Record<string, { steps?: Step[] }> };

const WORKFLOWS = join(import.meta.dirname, "../../../.github/workflows");
const WAIT = "npx tsx .sandcastle/agent-workflows/agent-slot/wait.ts";

const agentJobs = readdirSync(WORKFLOWS)
  .filter((file) => file.endsWith(".yml"))
  .flatMap((file) => {
    const { jobs } = parse(
      readFileSync(join(WORKFLOWS, file), "utf8")
    ) as Workflow;
    return Object.entries(jobs).map(([job, { steps = [] }]) => ({
      where: `${file}, job ${job}`,
      steps,
      agent: steps.findIndex(
        ({ env }) => env !== undefined && "CLAUDE_CODE_OAUTH_TOKEN" in env
      ),
    }));
  })
  .filter(({ agent }) => agent !== -1);

describe("every agent job waits for an agent slot", () => {
  it("finds the agent jobs", () => {
    expect(agentJobs.length).toBeGreaterThanOrEqual(6);
  });

  it.each(agentJobs)(
    "$where waits, under the step name the slots count, before its agent",
    ({ steps, agent }) => {
      const wait = steps.findIndex(({ name }) => name === SLOT_STEP);

      expect(wait).toBeGreaterThan(-1);
      expect(wait).toBeLessThan(agent);
      expect(steps[wait]?.run).toBe(WAIT);
    }
  );
});
