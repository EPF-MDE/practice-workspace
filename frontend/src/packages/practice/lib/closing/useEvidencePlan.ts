import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type CompetencyPage, PracticeService } from "@/client";
import { evidencePanelsKey } from "../evidence/EvidencePanel";
import {
  closingDrafts,
  type DraftScope,
  type EvidenceDraft,
  evidenceDrafts,
} from "../progress";
import { DONE, type Levels } from "./useSelfAssessment";

export function usePlan(
  scope: DraftScope,
  page: CompetencyPage,
  rated: Levels["rated"]
) {
  const { competency } = scope;
  const forDraft = Object.fromEntries(
    Object.entries(rated).filter(([, v]) => v.level !== DONE)
  );
  const draft = useQuery({
    queryKey: ["competency", competency, "draft", forDraft],
    queryFn: async () =>
      (
        await PracticeService.draftEvidencePlan({
          path: { competency },
          body: { levels: forDraft },
        })
      ).data,
    placeholderData: (previous) => previous,
  });
  const draftText = draft.data?.text ?? page.evidence_plan_draft;
  const [own, setOwn] = useState<string | null>(() =>
    closingDrafts.getPlan(scope)
  );
  const stored = page.evidence_plan;
  const ownStored = stored && !stored.drafted ? stored.text : null;
  const edit = (text: string | null) => {
    setOwn(text);
    closingDrafts.setPlan(scope, text);
  };
  return {
    text: own ?? ownStored ?? draftText,
    isDraft: own === null && ownStored === null,
    own,
    draftText,
    stored,
    edit,
  };
}

export type Plan = ReturnType<typeof usePlan>;

export function useExample(scope: DraftScope, stored: Plan["stored"]) {
  const [example, setExample] = useState(
    () => closingDrafts.getExample(scope) ?? stored?.example ?? ""
  );
  const type = (text: string) => {
    setExample(text);
    closingDrafts.setExample(scope, text);
  };
  return { example, type };
}

export function useEvidence(scope: DraftScope) {
  const [evidence, setEvidence] = useState<EvidenceDraft>(
    () => evidenceDrafts.get(scope) ?? { url: "", note: "" }
  );
  const draftEvidence = (next: EvidenceDraft | null) => {
    setEvidence(next ?? { url: "", note: "" });
    evidenceDrafts.set(scope, next);
  };
  return { evidence, draftEvidence };
}

async function sendPlan({
  competency,
  confirming,
  ...body
}: {
  competency: string;
  confirming: boolean;
  text: string;
  example: string;
  declaration: EvidenceDraft | null;
  drafted: boolean;
}) {
  if (confirming)
    return (
      await PracticeService.closeCompetency({ path: { competency }, body })
    ).data;
  return (
    await PracticeService.sendEvidencePlan({
      path: { competency },
      body: { text: body.text, drafted: body.drafted },
    })
  ).data;
}

export function useSendPlan({
  competency,
  plan,
  example,
  evidence: { evidence, draftEvidence },
}: {
  competency: string;
  plan: Plan;
  example: string;
  evidence: ReturnType<typeof useEvidence>;
}) {
  const queryClient = useQueryClient();
  const { stored, own, isDraft, draftText } = plan;
  const confirming = !stored?.confirmed || example.trim() !== stored.example;
  const declaring =
    !stored?.confirmed &&
    evidence.url.trim() !== "" &&
    evidence.note.trim() !== "";
  const planChanged =
    confirming ||
    (own !== null && own !== (stored?.text ?? "")) ||
    (isDraft && !!stored && draftText !== stored.text);
  const send = useMutation({
    mutationFn: () =>
      sendPlan({
        competency,
        confirming,
        text: plan.text,
        example,
        declaration: declaring ? evidence : null,
        drafted: isDraft,
      }),
    onSuccess: () => {
      plan.edit(null);
      if (declaring) draftEvidence(null);
      void queryClient.invalidateQueries({ queryKey: evidencePanelsKey });
      return queryClient.invalidateQueries({ queryKey: ["competency"] });
    },
  });
  return { send, confirming, planChanged };
}
