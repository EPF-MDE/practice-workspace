import { expect, type Locator, type Page } from "@playwright/test";
import { drawChain } from "./draw";

/**
 * The moves every Competency's Path shares, on the Demo course (demo-course/):
 * sign in, open a Competency from the opening page, answer a step whose
 * answer is locked, redraw, and send a Transfer. The closing step's moves are
 * in closing.ts. The path-c*.spec.ts files walk C1, C2 and C3 with them.
 */

export type Group = "OcéENS" | "MATHutrice";

/** The Demo course's service for each Group: the one name its blocks use. */
export const SERVICE: Record<Group, string> = {
  OcéENS: "Lendly",
  MATHutrice: "Skywatch",
};
export const OTHER: Record<Group, Group> = {
  OcéENS: "MATHutrice",
  MATHutrice: "OcéENS",
};

/** A Transfer's project, and a link to work in it, for the Evidence Project. */
export const BAKERY = "https://github.com/me/bakery";
export const LINK = "https://github.com/me/bakery/blob/main/README.md#L3";

/** Signs a roster Student in, sign-in faked. */
export async function signIn(page: Page, githubId: number) {
  await page.goto(`/auth/login?github_id=${githubId}`);
}

/** Opens a Competency from the opening page, by its link. */
export async function openCompetency(page: Page, competency: string) {
  await page.goto("/");
  await page.getByRole("link", { name: new RegExp(`^${competency} `) }).click();
  await expect(page).toHaveURL(new RegExp(`/competencies/${competency}$`));
}

export function step(page: Page, id: string): Locator {
  return page.locator(`section#${id}`);
}

export function path(page: Page): Locator {
  return page.getByRole("complementary", { name: "Your path" });
}

export async function expectFinished(page: Page, stepId: string) {
  await expect(path(page).getByTestId(`path-${stepId}`)).toHaveAttribute(
    "data-finished",
    "true"
  );
}

/** The page's step ids, in the order they are shown. */
export async function stepOrder(page: Page): Promise<string[]> {
  return page
    .locator("section[id]")
    .evaluateAll((sections) => sections.map((s) => s.id));
}

/** A step gives the Student their own Group's block, never the other Group's. */
export async function expectOwnGroupOnly(section: Locator, group: Group) {
  await expect(section).toContainText(SERVICE[group]);
  await expect(section).not.toContainText(SERVICE[OTHER[group]]);
}

/** Picks one option of a choice field, found by its label. */
export async function choose(section: Locator, label: string, option: string) {
  await section
    .getByRole("radiogroup", { name: label })
    .getByRole("radio", { name: option, exact: true })
    .check();
}

async function fill(section: Locator, fields: Record<string, string>) {
  for (const [name, value] of Object.entries(fields)) {
    await section.locator(`[name="${name}"]`).fill(value);
  }
}

/** Sends a step's fields as they stand, and expects its first version stored. */
export async function send(section: Locator) {
  await section.getByRole("button", { name: "Send my answer" }).click();
  await expect(section.getByTestId("sent")).toContainText("Version 1");
}

/**
 * Fills a step's text fields (by name) and sends them, after checking the
 * Instructor's answer is withheld; returns the answer the send releases.
 * Choice fields are picked with `choose` before.
 */
export async function answerStep(
  section: Locator,
  fields: Record<string, string>
): Promise<Locator> {
  await expect(section.getByTestId("answer-locked")).toBeVisible();
  await expect(section.getByTestId("answer")).toHaveCount(0);
  await fill(section, fields);
  await send(section);
  const answer = section.getByTestId("answer");
  await expect(answer.first()).toBeVisible();
  await expect(section.getByTestId("answer-locked")).toHaveCount(0);
  return answer;
}

/** Sends a step without an answer block (a Transfer). */
export async function sendFields(
  section: Locator,
  fields: Record<string, string>
) {
  await fill(section, fields);
  await send(section);
}

/**
 * Redraws in the step's canvas, checks the Reference Drawing is withheld until
 * the drawing is sent, then shown with its check points; returns them.
 */
export async function redraw(
  page: Page,
  section: Locator,
  labels: string[]
): Promise<Locator> {
  await expect(
    section
      .getByRole("figure", { name: "Example Drawing" })
      .locator(".tl-shape")
      .first()
  ).toBeVisible();
  await expect(section.getByTestId("reference-locked")).toBeVisible();
  await expect(section.getByTestId("reference-drawing")).toHaveCount(0);

  const canvas = section.getByRole("figure", { name: "Your drawing" });
  await drawChain(page, canvas.locator(".tl-canvas"), labels);
  await expect(canvas.locator(".tl-shape")).toHaveCount(labels.length * 2 - 1);
  await section.getByRole("button", { name: "Send my drawing" }).click();

  await expect(section.getByTestId("drawing-sent")).toContainText("Version 1");
  const reference = section.getByTestId("reference-drawing");
  await expect(
    reference
      .getByRole("figure", { name: "Reference Drawing" })
      .locator(".tl-shape")
      .first()
  ).toBeVisible();
  return reference.getByRole("checkbox");
}
