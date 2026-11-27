import { describe, expect, it } from "vitest";
import { AGENT_SLOTS, slotsOf, SLOT_STEP, WAIT_AT_MOST_MINUTES } from "./slots";
import { type Clock, waitForASlot } from "./wait-for-a-slot";

type Job = {
  id: number;
  runner: string;
  gate: "queued" | "waiting" | "passed" | "failed";
  since?: string;
  status?: string;
};

const STEP_OF: Record<
  Job["gate"],
  { status: string; conclusion: string | null }
> = {
  queued: { status: "queued", conclusion: null },
  waiting: { status: "in_progress", conclusion: null },
  passed: { status: "completed", conclusion: "success" },
  failed: { status: "completed", conclusion: "failure" },
};

const page = (run: number, jobs: Job[]) => ({
  jobs: jobs.map(({ id, runner, gate, since, status }) => ({
    id,
    run_id: run,
    status: status ?? "in_progress",
    runner_name: runner,
    steps: [
      { name: "Checkout", status: "completed", conclusion: "success" },
      {
        name: SLOT_STEP,
        ...STEP_OF[gate],
        started_at:
          gate === "queued" ? null : (since ?? "2026-11-26T17:09:00Z"),
      },
    ],
  })),
});

const fakeClock = (): Clock & { slept: number[] } => {
  let now = 0;
  const slept: number[] = [];
  return {
    slept,
    now: () => now,
    sleep: async (ms) => {
      slept.push(ms);
      now += ms;
    },
  };
};

const waits = (
  answers: ReturnType<typeof page>[][],
  me = { run: 1, runner: "runner-1" }
) => {
  const clock = fakeClock();
  const lines: string[] = [];
  let asked = 0;
  const outcome = waitForASlot({
    read: async () =>
      slotsOf(answers[Math.min(asked++, answers.length - 1)] ?? []),
    me,
    clock,
    log: (line) => lines.push(line),
  });
  return { outcome, clock, lines, asked: () => asked };
};

const me = (gate: Job["gate"] = "waiting", since?: string) =>
  page(1, [{ id: 10, runner: "runner-1", gate, since }]);

describe("waiting for an agent slot: taking one", () => {
  it("starts when a slot is free on two checks in a row", async () => {
    const { outcome, asked } = waits([[me()]]);

    expect(await outcome).toBe("start");
    expect(asked()).toBe(2);
  });

  it("waits while every slot is taken, and starts once one frees up", async () => {
    const busy = [
      page(2, [{ id: 20, runner: "a", gate: "passed" }]),
      page(3, [{ id: 30, runner: "b", gate: "passed" }]),
      me(),
    ];
    const freed = [page(2, [{ id: 20, runner: "a", gate: "passed" }]), me()];
    const { outcome, asked } = waits([busy, busy, busy, freed]);

    expect(await outcome).toBe("start");
    expect(asked()).toBe(5);
  });

  it("lets the run that started waiting first go first", async () => {
    const taken = page(2, [{ id: 20, runner: "a", gate: "passed" }]);
    const earlier = page(3, [
      { id: 30, runner: "b", gate: "waiting", since: "2026-11-26T17:08:00Z" },
    ]);
    const later = page(3, [
      { id: 30, runner: "b", gate: "waiting", since: "2026-11-26T17:10:00Z" },
    ]);

    const behind = waits([
      [taken, earlier, me("waiting", "2026-11-26T17:09:00Z")],
    ]);
    const first = waits([
      [taken, later, me("waiting", "2026-11-26T17:09:00Z")],
    ]);

    expect(await first.outcome).toBe("start");
    expect(await behind.outcome).toBe("timed-out");
  });
});

describe("waiting for an agent slot: counting them", () => {
  it(`does not let five runs waiting at once start more than ${AGENT_SLOTS}`, async () => {
    const runners = [1, 2, 3, 4, 5];
    const all = runners.map((n) =>
      page(n, [
        {
          id: n,
          runner: `runner-${n}`,
          gate: "waiting",
          since: "2026-11-26T17:09:00Z",
        },
      ])
    );
    const started = await Promise.all(
      runners.map(
        (n) => waits([all], { run: n, runner: `runner-${n}` }).outcome
      )
    );

    expect(started).toEqual([
      "start",
      "start",
      "timed-out",
      "timed-out",
      "timed-out",
    ]);
  });

  it("does not count a slot taken by a finished job, or one whose wait failed", async () => {
    const { outcome } = waits([
      [
        page(2, [{ id: 20, runner: "a", gate: "passed", status: "completed" }]),
        page(3, [{ id: 30, runner: "b", gate: "failed" }]),
        page(4, [{ id: 40, runner: "c", gate: "passed" }]),
        me(),
      ],
    ]);

    expect(await outcome).toBe("start");
  });

  it("waits until GitHub lists it as waiting before it takes a slot", async () => {
    const { outcome, asked } = waits([[me("queued")], [me("queued")], [me()]]);

    expect(await outcome).toBe("start");
    expect(asked()).toBe(4);
  });
});

describe("waiting for an agent slot: when GitHub is slow", () => {
  it("keeps waiting when GitHub does not answer", async () => {
    const clock = fakeClock();
    const lines: string[] = [];
    let asked = 0;
    const outcome = await waitForASlot({
      read: async () =>
        asked++ === 0 ? { failed: "GET answered 502" } : slotsOf([me()]),
      me: { run: 1, runner: "runner-1" },
      clock,
      log: (line) => lines.push(line),
    });

    expect(outcome).toBe("start");
    expect(lines[0]).toContain("GET answered 502");
  });

  it("gives up, saying so, when no slot frees up in time", async () => {
    const full = [
      page(2, [
        { id: 20, runner: "a", gate: "passed" },
        { id: 21, runner: "b", gate: "passed" },
      ]),
      me(),
    ];
    const { outcome, clock, lines } = waits([full]);

    expect(await outcome).toBe("timed-out");
    expect(clock.now()).toBeGreaterThanOrEqual(WAIT_AT_MOST_MINUTES * 60_000);
    expect(lines.at(-1)).toMatch(/^::error::No agent slot came free/);
  });
});
