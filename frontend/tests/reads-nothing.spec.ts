import { expect, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import { path, signIn } from "./helpers/path";

const IRIS = 5001;

const sidebar = (page: Page) => path(page).getByTestId("evidence-panel");

test("on a Course reading nothing until a Student declares, the Evidence panel asks for a declaration, then reads the one declared until it is withdrawn", async ({
  page,
}) => {
  await signIn(page, IRIS);
  await page.goto("/competencies/C1");

  await expect(
    sidebar(page).getByTestId("evidence-panel-unavailable")
  ).toContainText("You have not declared your Evidence Project yet");
  await expect(sidebar(page).getByTestId("evidence-panel-project")).toHaveCount(
    0
  );
  const close = closing(page);
  await expect(close.evidence.getByTestId("nothing-declared")).toBeVisible();
  await expect(
    close.evidence.getByTestId("roster-evidence-project")
  ).toHaveCount(0);

  await expect(
    await close.declare("https://github.com/iris/orchard", "The README first.")
  ).toContainText("Readable");
  await close.rate("C1.a", "Not yet");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.example.fill("The tree I planted.");
  await close.confirm.click();
  await expect(close.evidence.getByTestId("declared")).toContainText(
    "https://github.com/iris/orchard"
  );
  await expect(sidebar(page).getByTestId("evidence-panel-project")).toHaveText(
    "iris/orchard"
  );

  await close.evidence
    .getByRole("button", {
      name: "Withdraw it: nothing is read until you declare another",
    })
    .click();
  await expect(close.evidence.getByTestId("nothing-declared")).toBeVisible();
  await expect(
    sidebar(page).getByTestId("evidence-panel-unavailable")
  ).toContainText("You have not declared your Evidence Project yet");
});
