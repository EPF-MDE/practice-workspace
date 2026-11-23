import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { type CompetencyPage, PracticeService } from "@/client";
import { Html } from "./lib/Html";
import {
  type DraftScope,
  finishedSteps,
  greyedSteps,
  readSteps,
  startedAt,
} from "./lib/progress";
import { Sidebar } from "./lib/Sidebar";
import { StepSection } from "./lib/StepSection";
import { pathKey } from "./lib/pathKeys";

function progressOf(page: CompetencyPage, read: string[]) {
  const { steps } = page;
  const finished = finishedSteps(steps, read);
  if (page.evidence_plan?.confirmed)
    for (const step of steps)
      if (step.kind === "closing") finished.add(step.id);
  const current = (
    steps.find((s) => !finished.has(s.id) && !s.optional) ?? steps.at(-1)
  )?.id;
  return { finished, greyed: greyedSteps(steps, finished), current };
}

function PathHeader({ page }: { page: CompetencyPage }) {
  return (
    <header className="flex flex-col gap-2">
      <Link to="/" className="text-sm underline">
        Back to the workspace
      </Link>
      <h1 className="text-3xl font-semibold">
        {page.competency}: {page.title}
      </h1>
      {page.closed && (
        <output className="block rounded-md border p-3">
          The workspace closed on {new Date(page.closes_at).toLocaleString()}.
          You can read everything, but no longer send answers or questions.
        </output>
      )}
      <Html html={page.intro_html} />
    </header>
  );
}

function PathView({
  scope,
  page,
}: {
  scope: DraftScope;
  page: CompetencyPage;
}) {
  const [read, setRead] = useState(() => readSteps.get(scope));
  const started = useMemo(
    () =>
      startedAt({ studentId: scope.studentId, competency: scope.competency }),
    [scope.studentId, scope.competency]
  );
  const { finished, greyed, current } = progressOf(page, read);
  return (
    <div className="mx-auto grid max-w-7xl gap-8 p-6 lg:grid-cols-[18rem_1fr]">
      <Sidebar
        competency={scope.competency}
        steps={page.steps}
        finished={finished}
        greyed={greyed}
        startedAt={started}
        evidencePlan={page.evidence_plan?.text ?? page.evidence_plan_draft}
        currentStep={current}
      />
      <main className="flex min-w-0 flex-col gap-8">
        <PathHeader page={page} />
        {page.steps.map((step) => (
          <StepSection
            key={step.id}
            {...scope}
            step={step}
            page={page}
            closed={page.closed}
            finished={finished.has(step.id)}
            greyed={greyed.has(step.id)}
            licenseKey={page.tldraw_license_key}
            onRead={() => setRead(readSteps.get(scope))}
          />
        ))}
      </main>
    </div>
  );
}

export function Path({
  studentId,
  competency,
}: {
  studentId: number;
  competency: string;
}) {
  const page = useQuery({
    queryKey: pathKey(competency),
    queryFn: async () =>
      (await PracticeService.competencyPage({ path: { competency } })).data,
  });

  if (page.isPending) return <main className="p-8">Loading {competency}…</main>;
  if (page.isError || !page.data)
    return (
      <main className="p-8">
        This Competency cannot be shown.{" "}
        <Link to="/">Back to the workspace</Link>
      </main>
    );
  return <PathView scope={{ studentId, competency }} page={page.data} />;
}
