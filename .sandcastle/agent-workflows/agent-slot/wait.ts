import { required } from "../shared/common";
import { JobsPage, RunsPage, type Slots, slotsOf } from "./slots";
import { waitForASlot } from "./wait-for-a-slot";

const AGENT_WORKFLOWS = ".github/workflows/agent-";

const repo = required("GH_REPO");
const token = required("GITHUB_TOKEN");
const run = Number(required("GITHUB_RUN_ID"));
const runner = required("RUNNER_NAME");

class Failed extends Error {}

const get = async (path: string): Promise<unknown> => {
  const response = await fetch(`https://api.github.com/repos/${repo}/${path}`, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!response.ok) {
    throw new Failed(`GET ${path} answered ${response.status}`);
  }
  return response.json();
};

const read = async (): Promise<Slots | { failed: string }> => {
  try {
    const runs = RunsPage.parse(
      await get("actions/runs?status=in_progress&per_page=100")
    ).workflow_runs.filter(({ path }) => path.startsWith(AGENT_WORKFLOWS));
    const pages = await Promise.all(
      runs.map(async ({ id }) =>
        JobsPage.parse(
          await get(`actions/runs/${id}/jobs?filter=latest&per_page=100`)
        )
      )
    );
    return slotsOf(pages);
  } catch (error) {
    return { failed: error instanceof Error ? error.message : String(error) };
  }
};

const outcome = await waitForASlot({
  read,
  me: { run, runner },
  clock: {
    now: () => Date.now(),
    sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  },
  log: (line) => process.stdout.write(`${line}\n`),
});

process.exit(outcome === "start" ? 0 : 1);
