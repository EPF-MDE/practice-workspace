import { useQuery } from "@tanstack/react-query";
import { PracticeService } from "@/client";

export const evidencePanelsKey = ["evidence-panel"];

export const evidencePanelKey = (competency: string) => [
  ...evidencePanelsKey,
  competency,
];

export function useEvidencePanel(competency: string) {
  return useQuery({
    queryKey: evidencePanelKey(competency),
    queryFn: async () =>
      (await PracticeService.evidencePanelView({ path: { competency } })).data,
  });
}
