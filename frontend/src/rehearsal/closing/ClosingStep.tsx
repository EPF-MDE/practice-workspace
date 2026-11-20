import type { CompetencyPage, PointBlock, StepOut } from "@/client";
import { EvidenceProject } from "../fork/EvidenceProject";
import { ForkPanelView, openQuestion } from "../fork/ForkPanel";
import { type DraftScope } from "../progress";
import { ExampleField, PlanEditor, PlanSendBar } from "./PracticePlanForm";
import { SelfAssessmentForm } from "./SelfAssessmentForm";
import {
  useEvidence,
  useExample,
  usePlan,
  useSendPlan,
} from "./usePracticePlan";
import { hints, useLevels, useSendLevels } from "./useSelfAssessment";

type Props = DraftScope & {
  step: StepOut;
  page: CompetencyPage;
};

/** The closing step's state: the levels, then the plan drafted from them, and their sends. */
function useClosing({ page, ...scope }: DraftScope & { page: CompetencyPage }) {
  const levels = useLevels(scope, page);
  const sendLevels = useSendLevels(scope, page, levels.rated);
  const plan = usePlan(scope, page, levels.rated);
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

/**
 * The closing step: a level per point, the Practice Plan drafted as the
 * Student rates, their own text winning once edited, and one send that
 * confirms it with an example for the Eval.
 */
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
      <ForkPanelView
        competency={competency}
        title="Your fork, before you choose your Evidence Project"
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
          The Reading Day has passed: your Self-assessment and Practice Plan no
          longer change.
        </output>
      )}
    </div>
  );
}
