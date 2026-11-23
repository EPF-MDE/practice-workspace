import { useSuspenseQuery } from "@tanstack/react-query";
import type { CompetencyPage, PointBlock, StepOut } from "@/client";
import { courseQuery } from "@/course";
import { EvidenceProject } from "@/packages/evidence/EvidenceProject";
import {
  EvidencePanelView,
  openQuestion,
} from "@/packages/evidence/EvidencePanel";
import { type DraftScope } from "@/packages/shared/drafts";
import { ExampleField, PlanEditor, PlanSendBar } from "./EvidencePlanForm";
import { SelfAssessmentForm } from "./SelfAssessmentForm";
import {
  useEvidence,
  useExample,
  usePlan,
  useSendPlan,
} from "./useEvidencePlan";
import { hints, useLevels, useSendLevels } from "./useSelfAssessment";

type Props = DraftScope & {
  step: StepOut;
  page: CompetencyPage;
};

function useClosing({ page, ...scope }: DraftScope & { page: CompetencyPage }) {
  const { data: course } = useSuspenseQuery(courseQuery);
  const levels = useLevels(scope, page, course);
  const sendLevels = useSendLevels(scope, page, levels.rated);
  const plan = usePlan(scope, page, levels);
  const example = useExample(scope, plan.stored);
  const evidence = useEvidence(scope);
  const sending = useSendPlan({
    competency: scope.competency,
    plan,
    example: example.example,
    evidence,
  });
  return { levels, sendLevels, plan, example, evidence, sending };
}

export function ClosingStep({ studentId, competency, step, page }: Props) {
  const points = step.blocks.filter(
    (b): b is PointBlock & { type: "point" } => b.type === "point"
  );
  const { levels, sendLevels, plan, example, evidence, sending } = useClosing({
    studentId,
    competency,
    page,
  });
  const over = page.reading_day_passed;

  return (
    <div className="flex flex-col gap-6">
      <SelfAssessmentForm
        points={points}
        page={page}
        levels={levels}
        hints={hints(studentId, page)}
        sendLevels={sendLevels}
      />
      <PlanEditor plan={plan} over={over} />
      <EvidencePanelView
        competency={competency}
        onMyWorkMissing={() => openQuestion(step.id)}
      />
      <EvidenceProject
        competency={competency}
        draft={evidence.evidence}
        onDraft={evidence.draftEvidence}
        ridesWithClose={!plan.stored?.confirmed}
        over={over}
      />
      <ExampleField example={example} over={over} />
      <PlanSendBar
        plan={plan}
        example={example.example}
        over={over}
        sending={sending}
      />
      {over && (
        <output className="block rounded-md border p-3 text-sm">
          The Reading Day has passed: your Self-assessment and Evidence Plan no
          longer change.
        </output>
      )}
    </div>
  );
}
