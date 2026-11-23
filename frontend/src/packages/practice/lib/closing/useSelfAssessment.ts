import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  type CheckPointOut,
  type CompetencyPage,
  type LevelOut,
  PracticeService,
} from "@/client";
import type { Course } from "@/course";
import {
  closingDrafts,
  type DraftScope,
  type LevelDraft,
} from "@/packages/shared/drafts";
import { pathKey } from "@/packages/shared/pathKeys";

const LINK = /^https:\/\/(github\.com|gitlab\.com)\/[\w.-]+\/[\w.-]+(\/\S*)?$/;

function ticks(studentId: number, page: CompetencyPage) {
  const out: Record<string, { local: boolean; missed: string[] }> = {};
  const scope = { studentId, competency: page.competency };
  for (const step of page.steps) {
    const local = closingDrafts.getTicks(scope, step.id);
    if (local !== null) out[step.id] = { local: true, missed: local };
    else if (step.missed_check_points)
      out[step.id] = { local: false, missed: step.missed_check_points };
  }
  return out;
}

export function hints(
  studentId: number,
  page: CompetencyPage
): Record<string, CheckPointOut[]> {
  const missed = ticks(studentId, page);
  const checks = page.steps.flatMap((step) =>
    step.blocks.flatMap((block) =>
      block.type === "reference-drawing"
        ? (block.check_points ?? []).filter((check) =>
            missed[step.id]?.missed.includes(check.id)
          )
        : []
    )
  );
  const out: Record<string, CheckPointOut[]> = {};
  for (const check of checks)
    out[check.point] = [...(out[check.point] ?? []), check];
  return out;
}

function ratedLevels(levels: Record<string, LevelDraft>, topLevel: LevelOut) {
  return Object.fromEntries(
    Object.entries(levels)
      .filter(([, v]) => v.level)
      .map(([p, v]) => [
        p,
        {
          level: v.level,
          link: v.level === topLevel.id ? v.link.trim() : null,
        },
      ])
  );
}

export function useLevels(
  scope: DraftScope,
  page: CompetencyPage,
  course: Course
) {
  const { levels: scale, topLevel } = course;
  const sent = page.self_assessment?.levels ?? {};
  const [levels, setLevels] = useState<Record<string, LevelDraft>>(() => ({
    ...Object.fromEntries(
      Object.entries(sent).map(([p, v]) => [
        p,
        { level: v.level, link: v.link ?? "" },
      ])
    ),
    ...closingDrafts.getLevels(scope),
  }));
  const rate = (point: string, next: Partial<LevelDraft>) => {
    const all = {
      ...levels,
      [point]: { ...(levels[point] ?? { level: "", link: "" }), ...next },
    };
    setLevels(all);
    closingDrafts.setLevels(scope, all);
  };
  const rated = ratedLevels(levels, topLevel);
  const changed =
    Object.keys(rated).length > 0 &&
    (Object.keys(rated).length !== Object.keys(sent).length ||
      Object.entries(rated).some(
        ([p, v]) =>
          sent[p]?.level !== v.level || (sent[p]?.link ?? null) !== v.link
      ) ||
      Object.values(ticks(scope.studentId, page)).some((t) => t.local));
  const missingLink = Object.entries(rated).find(
    ([, v]) => v.level === topLevel.id && !LINK.test(v.link ?? "")
  );
  return { scale, topLevel, levels, rate, sent, rated, changed, missingLink };
}

export type Levels = ReturnType<typeof useLevels>;

export function useSendLevels(
  scope: DraftScope,
  page: CompetencyPage,
  rated: Levels["rated"]
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const local = Object.fromEntries(
        Object.entries(ticks(scope.studentId, page))
          .filter(([, t]) => t.local)
          .map(([s, t]) => [s, t.missed])
      );
      return (
        await PracticeService.sendSelfAssessment({
          path: { competency: scope.competency },
          body: { levels: rated, missed_check_points: local },
        })
      ).data;
    },
    onSuccess: () => {
      for (const s of page.steps) closingDrafts.clearTicks(scope, s.id);
      return queryClient.invalidateQueries({
        queryKey: pathKey(scope.competency),
      });
    },
  });
}
