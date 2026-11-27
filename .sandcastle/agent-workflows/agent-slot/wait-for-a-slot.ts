import {
  AGENT_SLOTS,
  CHECK_EVERY_MS,
  CONFIRM_AFTER_MS,
  type Slots,
  turnOf,
  WAIT_AT_MOST_MINUTES,
} from "./slots";

export type Clock = {
  now: () => number;
  sleep: (ms: number) => Promise<void>;
};

export type Read = () => Promise<Slots | { failed: string }>;

export type Outcome = "start" | "timed-out";

export const waitForASlot = async ({
  read,
  me,
  clock,
  log,
}: {
  read: Read;
  me: { run: number; runner: string };
  clock: Clock;
  log: (line: string) => void;
}): Promise<Outcome> => {
  const deadline = clock.now() + WAIT_AT_MOST_MINUTES * 60_000;
  let freeOnce = false;
  while (clock.now() < deadline) {
    const slots = await read();
    if ("failed" in slots) {
      freeOnce = false;
      log(`::warning::Could not count the agent runs: ${slots.failed}`);
      await clock.sleep(CHECK_EVERY_MS);
      continue;
    }
    const turn = turnOf(slots, me);
    if (turn.kind === "start" && freeOnce) {
      log(`A slot is free (${AGENT_SLOTS} at most). The agent starts.`);
      return "start";
    }
    if (turn.kind === "start") {
      freeOnce = true;
      log("A slot looks free. Checking once more before taking it.");
      await clock.sleep(CONFIRM_AFTER_MS);
      continue;
    }
    freeOnce = false;
    if (turn.kind === "unseen") {
      log("GitHub does not list this job as waiting yet.");
      await clock.sleep(CONFIRM_AFTER_MS);
      continue;
    }
    log(
      `${turn.taken} of ${AGENT_SLOTS} agent slots taken, ${turn.ahead} run(s) waiting ahead of this one.`
    );
    await clock.sleep(CHECK_EVERY_MS);
  }
  log(
    `::error::No agent slot came free in ${WAIT_AT_MOST_MINUTES} minutes: ${AGENT_SLOTS} agent runs kept them all. The agent did not start. Put the label back to try again.`
  );
  return "timed-out";
};
