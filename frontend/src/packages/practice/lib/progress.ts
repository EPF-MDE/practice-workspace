import { AxiosError } from "axios";
import type { StepOut } from "@/client";

export type DraftScope = { studentId: number; competency: string };

function key(scope: DraftScope, ...rest: string[]) {
  return ["cws", scope.studentId, scope.competency, ...rest].join(":");
}

function read<T>(name: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(name);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function write(name: string, value: unknown) {
  localStorage.setItem(name, JSON.stringify(value));
}

export const drafts = {
  get: (scope: DraftScope, step: string) =>
    read<Record<string, string>>(key(scope, "draft", step), {}),
  set: (scope: DraftScope, step: string, fields: Record<string, string>) =>
    write(key(scope, "draft", step), fields),
  getQuestion: (scope: DraftScope, step: string) =>
    read<string>(key(scope, "question", step), ""),
  setQuestion: (scope: DraftScope, step: string, text: string) =>
    write(key(scope, "question", step), text),
  getDrawing: (scope: DraftScope, step: string) =>
    read<Record<string, unknown> | null>(key(scope, "drawing", step), null),
  setDrawing: (scope: DraftScope, step: string, snapshot: unknown) => {
    try {
      write(key(scope, "drawing", step), snapshot);
      return true;
    } catch {
      return false;
    }
  },
};

export type LevelDraft = { level: string; link: string };

export const closingDrafts = {
  getTicks: (scope: DraftScope, step: string) =>
    read<string[] | null>(key(scope, "ticks", step), null),
  setTicks: (scope: DraftScope, step: string, missed: string[]) =>
    write(key(scope, "ticks", step), missed),
  clearTicks: (scope: DraftScope, step: string) =>
    localStorage.removeItem(key(scope, "ticks", step)),
  getLevels: (scope: DraftScope) =>
    read<Record<string, LevelDraft>>(key(scope, "levels"), {}),
  setLevels: (scope: DraftScope, levels: Record<string, LevelDraft>) =>
    write(key(scope, "levels"), levels),
  getPlan: (scope: DraftScope) => read<string | null>(key(scope, "plan"), null),
  setPlan: (scope: DraftScope, text: string | null) =>
    text === null
      ? localStorage.removeItem(key(scope, "plan"))
      : write(key(scope, "plan"), text),
  getExample: (scope: DraftScope) =>
    read<string | null>(key(scope, "example"), null),
  setExample: (scope: DraftScope, text: string) =>
    write(key(scope, "example"), text),
};

export type EvidenceDraft = { url: string; note: string };

export const evidenceDrafts = {
  get: (scope: DraftScope) =>
    read<EvidenceDraft | null>(key(scope, "evidence"), null),
  set: (scope: DraftScope, draft: EvidenceDraft | null) =>
    draft === null
      ? localStorage.removeItem(key(scope, "evidence"))
      : write(key(scope, "evidence"), draft),
};

export const readSteps = {
  get: (scope: DraftScope) => read<string[]>(key(scope, "read"), []),
  add: (scope: DraftScope, step: string) =>
    write(key(scope, "read"), [...new Set([...readSteps.get(scope), step])]),
};

export function startedAt(scope: DraftScope): number {
  const name = key(scope, "started");
  const started = read<number | null>(name, null);
  if (started !== null) return started;
  const now = Date.now();
  write(name, now);
  return now;
}

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

export function errorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response)
      return "The workspace cannot be reached: your text is kept, try again.";
  }
  return "Sending failed: your text is kept, try again.";
}
