import { expect, type Locator, type Page } from "@playwright/test";
import { drawChain, shapesOfChain } from "./draw";

export type Group = "Willow" | "Cedar";

export const SERVICE: Record<Group, string> = {
  Willow: "Lendly",
  Cedar: "Skywatch",
};
export const OTHER: Record<Group, Group> = {
  Willow: "Cedar",
  Cedar: "Willow",
};

export const BAKERY = "https://github.com/me/bakery";
export const LINK = "https://github.com/me/bakery/blob/main/README.md#L3";

export async function signIn(page: Page, githubId: number) {
  await page.goto(`/auth/login?github_id=${githubId}`);
}

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

export async function stepOrder(page: Page): Promise<string[]> {
  return page
    .locator("section[id]")
    .evaluateAll((sections) => sections.map((s) => s.id));
}

export async function expectOwnGroupOnly(section: Locator, group: Group) {
  await expect(section).toContainText(SERVICE[group]);
  await expect(section).not.toContainText(SERVICE[OTHER[group]]);
}

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

export async function send(section: Locator) {
  await section.getByRole("button", { name: "Send my answer" }).click();
  await expect(section.getByTestId("sent")).toContainText("Version 1");
}

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

export async function sendFields(
  section: Locator,
  fields: Record<string, string>
) {
  await fill(section, fields);
  await send(section);
}

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
  await expect(canvas.locator(".tl-shape")).toHaveCount(shapesOfChain(labels));
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
