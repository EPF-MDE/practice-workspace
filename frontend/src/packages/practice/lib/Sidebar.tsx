import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import type { CompetencyOut, StepOut } from "@/client";
import { cn } from "@/lib/utils";
import {
  EvidencePanelView,
  openQuestion,
} from "@/packages/evidence/EvidencePanel";

function clock(minutes: number) {
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

function useMinutesSince(start: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, []);
  return Math.max(0, Math.floor((now - start) / 60_000));
}

function schedule(steps: StepOut[]) {
  return steps.map((step, index) => {
    const from = steps
      .slice(0, index)
      .reduce((sum, before) => sum + before.minutes, 0);
    return { step, from, to: from + step.minutes };
  });
}

function session(competencies: CompetencyOut[]) {
  return competencies.map((competency, index) => {
    const from = competencies
      .slice(0, index)
      .reduce((sum, before) => sum + before.minutes, 0);
    return { competency, from, to: from + competency.minutes };
  });
}

type Slot = ReturnType<typeof session>[number];

function slotOf(competencies: CompetencyOut[], competency: string) {
  return session(competencies).find(
    (slot) => slot.competency.id === competency
  );
}

type PathProps = {
  competency: string;
  competencies: CompetencyOut[];
  steps: StepOut[];
  finished: Set<string>;
  greyed: Set<string>;
};

function PathStep({
  step,
  from,
  to,
  offset,
  done,
  greyed,
}: ReturnType<typeof schedule>[number] & {
  offset: number;
  done: boolean;
  greyed: boolean;
}) {
  return (
    <li
      data-testid={`path-${step.id}`}
      data-finished={done}
      data-greyed={greyed}
      className={cn("flex items-start gap-2", greyed && "opacity-40")}
    >
      <span className="mt-0.5 w-4 shrink-0">
        {done && <Check aria-label="finished" className="size-4" />}
      </span>
      <a className="flex-1 hover:underline" href={`#${step.id}`}>
        {step.title}
        {step.optional && (
          <span className="text-muted-foreground"> (optional)</span>
        )}
        {step.waits_for && (
          <span
            className="text-muted-foreground"
            data-testid={`waits-${step.id}`}
          >
            {" "}
            (after {step.waits_for.title})
          </span>
        )}
      </a>
      {step.minutes > 0 && (
        <span className="text-muted-foreground tabular-nums">
          {clock(offset + from)}–{clock(offset + to)}
        </span>
      )}
    </li>
  );
}

function PathSection({
  competency,
  competencies,
  steps,
  finished,
  greyed,
}: PathProps) {
  const offset = slotOf(competencies, competency)?.from ?? 0;
  return (
    <section className="rounded-lg border p-4">
      <h2 className="font-semibold">Your path in {competency}</h2>
      <ol className="mt-2 flex flex-col gap-1 text-sm">
        {schedule(steps).map((slot) => (
          <PathStep
            key={slot.step.id}
            {...slot}
            offset={offset}
            done={finished.has(slot.step.id)}
            greyed={greyed.has(slot.step.id)}
          />
        ))}
      </ol>
    </section>
  );
}

function PlanSection({
  competency,
  evidencePlan,
}: {
  competency: string;
  evidencePlan: string;
}) {
  return (
    <section className="rounded-lg border p-4 text-sm">
      <h2 className="font-semibold">Your Evidence Plan</h2>
      {evidencePlan ? (
        <p
          data-testid="sidebar-plan"
          className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap"
        >
          {evidencePlan}
        </p>
      ) : (
        <p className="mt-2 text-muted-foreground">
          It fills as you send your Self-assessment, at the end of {competency}.
        </p>
      )}
    </section>
  );
}

function TimeSection({
  competency,
  competencies,
  startedAt,
}: {
  competency: string;
  competencies: CompetencyOut[];
  startedAt: number;
}) {
  const spent = useMinutesSince(startedAt);
  const slots = session(competencies);
  const total = slots.at(-1)?.to ?? 0;
  return (
    <section className="rounded-lg border p-4 text-sm">
      <h2 className="font-semibold">Time</h2>
      <p data-testid="time-spent">
        You have spent {spent} min on {competency}, out of{" "}
        {slotOf(competencies, competency)?.competency.minutes}.
      </p>
      <p className="mt-2 text-muted-foreground">
        The session:{" "}
        {slots
          .map(
            (slot: Slot) =>
              `${slot.competency.id} ${clock(slot.from)}–${clock(slot.to)}`
          )
          .join(", ")}
        , {clock(total)} in all.
      </p>
    </section>
  );
}

export function Sidebar({
  startedAt,
  evidencePlan,
  currentStep,
  ...path
}: PathProps & {
  startedAt: number;
  evidencePlan: string;
  currentStep: string | undefined;
}) {
  const { competency, competencies } = path;
  return (
    <aside
      aria-label="Your path"
      className="flex flex-col gap-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto"
    >
      <PathSection {...path} />
      <EvidencePanelView
        competency={competency}
        onMyWorkMissing={() => currentStep && openQuestion(currentStep)}
      />
      <PlanSection competency={competency} evidencePlan={evidencePlan} />
      <TimeSection
        competency={competency}
        competencies={competencies}
        startedAt={startedAt}
      />
    </aside>
  );
}
