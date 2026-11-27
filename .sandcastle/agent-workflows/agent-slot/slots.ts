import { z } from "zod";

export const AGENT_SLOTS = 2;
export const SLOT_STEP = "Wait for an agent slot";

const Step = z.object({
  name: z.string(),
  status: z.string(),
  conclusion: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
});

export const JobsPage = z.object({
  jobs: z.array(
    z.object({
      id: z.number(),
      run_id: z.number(),
      status: z.string(),
      runner_name: z.string().nullable().optional(),
      steps: z.array(Step).optional(),
    })
  ),
});

export const RunsPage = z.object({
  workflow_runs: z.array(z.object({ id: z.number(), path: z.string() })),
});

export type Waiting = {
  job: number;
  run: number;
  runner: string | null;
  since: string;
};

export type Slots = { taken: number; waiting: Waiting[] };

export const slotsOf = (pages: z.infer<typeof JobsPage>[]): Slots => {
  let taken = 0;
  const waiting: Waiting[] = [];
  for (const job of pages.flatMap(({ jobs }) => jobs)) {
    const step = job.steps?.find(({ name }) => name === SLOT_STEP);
    if (job.status !== "in_progress" || step === undefined) continue;
    if (step.status === "completed" && step.conclusion === "success") {
      taken += 1;
    }
    if (step.status === "in_progress" && step.started_at) {
      waiting.push({
        job: job.id,
        run: job.run_id,
        runner: job.runner_name ?? null,
        since: step.started_at,
      });
    }
  }
  return { taken, waiting };
};

const ahead = (a: Waiting, b: Waiting): boolean =>
  a.since < b.since || (a.since === b.since && a.job < b.job);

export type Turn =
  | { kind: "start" }
  | { kind: "wait"; taken: number; ahead: number }
  | { kind: "unseen" };

export const turnOf = (
  slots: Slots,
  me: { run: number; runner: string }
): Turn => {
  const mine = slots.waiting.find(
    ({ run, runner }) => run === me.run && runner === me.runner
  );
  if (mine === undefined) return { kind: "unseen" };
  const before = slots.waiting.filter((other) => ahead(other, mine)).length;
  return slots.taken + before < AGENT_SLOTS
    ? { kind: "start" }
    : { kind: "wait", taken: slots.taken, ahead: before };
};

export const CHECK_EVERY_MS = 60_000;
export const CONFIRM_AFTER_MS = 15_000;
export const WAIT_AT_MOST_MINUTES = 180;
