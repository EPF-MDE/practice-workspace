import { AxiosError } from "axios";
import type { StepOut } from "@/client";

/**
 * What the browser keeps until the Student sends it: drafts, steps read, the
 * time the Competency was opened. Nothing here reaches the Store (no
 * autosave), and a reload loses nothing.
 */

/** Whose drafts they are, and on which Competency's page. */
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
  /** The Student's canvas, as a tldraw snapshot, while they draw. */
  getDrawing: (scope: DraftScope, step: string) =>
    read<Record<string, unknown> | null>(key(scope, "drawing", step), null),
  /** False when the browser refused to keep it (storage full). */
  setDrawing: (scope: DraftScope, step: string, snapshot: unknown) => {
    try {
      write(key(scope, "drawing", step), snapshot);
      return true;
    } catch {
      return false;
    }
  },
};

/** A point's level as the Student is choosing it, before sending. */
export type LevelDraft = { level: string; link: string };

/** The closing step's drafts: kept here until sent with the Self-assessment or the closing step. */
export const closingDrafts = {
  /** The check points ticked as missed on a drawing, until the Self-assessment carries them. */
  getTicks: (scope: DraftScope, step: string) =>
    read<string[] | null>(key(scope, "ticks", step), null),
  setTicks: (scope: DraftScope, step: string, missed: string[]) =>
    write(key(scope, "ticks", step), missed),
  /** Once sent: the Store's ticks are the ones shown again. */
  clearTicks: (scope: DraftScope, step: string) =>
    localStorage.removeItem(key(scope, "ticks", step)),
  getLevels: (scope: DraftScope) =>
    read<Record<string, LevelDraft>>(key(scope, "levels"), {}),
  setLevels: (scope: DraftScope, levels: Record<string, LevelDraft>) =>
    write(key(scope, "levels"), levels),
  /** The Student's own Evidence Plan text, once they edit it: from then on it wins over the draft. */
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

/** An Evidence Project being declared: kept here until declared, or sent with the closing step. */
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

/** When the Student first opened this Competency's page, in this browser. */
export function startedAt(scope: DraftScope): number {
  const name = key(scope, "started");
  const started = read<number | null>(name, null);
  if (started !== null) return started;
  const now = Date.now();
  write(name, now);
  return now;
}

const isSent = (step: StepOut) => Boolean(step.sent || step.drawing);

/**
 * A step is finished once its answer or drawing is sent; a reading step once
 * the Student says they read it, or once they sent a later step.
 */
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

/**
 * Steps more than one past the first unfinished step: greyed, never locked.
 * The optional redraw is never waited for.
 */
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
