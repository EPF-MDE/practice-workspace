import type { StepOut } from "@/client";

const isSent = (step: StepOut) => Boolean(step.sent || step.drawing);

export function finishedSteps(steps: StepOut[], read: string[]): Set<string> {
  const finished = new Set<string>();
  const lastSent = steps.reduce(
    (last, step, index) => (isSent(step) && !step.optional ? index : last),
    -1
  );
  steps.forEach((step, index) => {
    if (isSent(step)) finished.add(step.id);
    else if (
      step.kind === "read" &&
      (read.includes(step.id) || index < lastSent)
    )
      finished.add(step.id);
  });
  return finished;
}

export function greyedSteps(
  steps: StepOut[],
  finished: Set<string>
): Set<string> {
  const first = steps.findIndex(
    (step) => !step.optional && !finished.has(step.id)
  );
  if (first === -1) return new Set();
  return new Set(
    steps.filter((_, index) => index > first + 1).map((s) => s.id)
  );
}
