import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { type CompetencyPage as PageData, PracticeService } from "@/client";
import { Html } from "@/practice/Html";
import {
  type DraftScope,
  finishedSteps,
  greyedSteps,
  readSteps,
  startedAt,
} from "@/practice/progress";
import { Sidebar } from "@/practice/Sidebar";
import { StepSection } from "@/practice/StepSection";
import { requireStudent } from "@/session";

export const Route = createFileRoute("/competencies/$competency")({
  beforeLoad: async ({ context }) => ({
    student: await requireStudent(context.queryClient),
  }),
  component: CompetencyPage,
});

/** Which steps are finished, which greyed, and which one the Student is on. */
function progressOf(page: PageData, read: string[]) {
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

function PageHeader({ page }: { page: PageData }) {
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

function CompetencyView({
  scope,
  page,
}: {
  scope: DraftScope;
  page: PageData;
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
        <PageHeader page={page} />
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

function CompetencyPage() {
  const { competency } = Route.useParams();
  const { student } = Route.useRouteContext();
  const page = useQuery({
    queryKey: ["competency", competency],
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
  return (
    <CompetencyView
      scope={{ studentId: student.github_id, competency }}
      page={page.data}
    />
  );
}
