import { expect, type Locator, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import { path, signIn } from "./helpers/path";

// Students of the Demo roster (demo-course/roster.csv) that only this file
// signs in. The Repository reading is the fake one: Alan's reading is
// backend/tests/fixtures/repository-readings/alan-oceens.json, Hedy's repository reads
// as empty. Access: a repository whose name says "private" is not readable.
const ALAN = 1041; // OcéENS, work on a branch of his Evidence Project
const HEDY = 1042; // MATHutrice, an empty Evidence Project

const sidebar = (page: Page) => path(page).getByTestId("evidence-panel");

test("the Evidence panel says what the Reading Day would find, then the closing step declares an Evidence Project", async ({
  page,
}) => {
  await signIn(page, ALAN);
  await page.goto("/competencies/C1");
  await readThePanel(page);

  // The closing step brings the panel forward, with the Evidence Project.
  const close = closing(page);
  await expect(close.section.getByTestId("evidence-panel")).toContainText(
    "feature/order-timeout"
  );
  await checkAccess(close.evidence);

  // The declaration rides with the closing step's one send.
  await close.rate("C1.a", "I understand");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.example.fill("The orders timeout on my bakery.");
  await close.confirm.click();
  await expect(close.section.getByTestId("plan-sent")).toContainText(
    "Version 1 confirmed"
  );

  // That Competency's Evidence Project facts are greyed.
  const panel = sidebar(page);
  await expect(panel.getByTestId("evidence-panel-greyed")).toHaveText(
    "The Reading Day reads alan/bakery for C1, instead of your Evidence Project."
  );
  await expect(close.evidence.getByTestId("declared")).toContainText(
    "https://github.com/alan/bakery"
  );

  // Withdrawn: the Evidence Project is read again.
  await close.evidence
    .getByRole("button", { name: "Withdraw it: back to my Evidence Project" })
    .click();
  await expect(close.evidence).toContainText("Nothing else declared");
  await expect(panel.getByTestId("evidence-panel-greyed")).toHaveCount(0);
});

/** Facts naming their point, when they were read, a refresh, and a way to ask. */
async function readThePanel(page: Page) {
  const panel = sidebar(page);
  await expect(panel.getByTestId("fact-C1")).toContainText(
    "feature/order-timeout changes 3 files"
  );
  await expect(panel.getByTestId("fact-C1")).toContainText("→ C1");
  await expect(panel.getByTestId("evidence-panel-not-judged")).toContainText(
    "does not judge them"
  );

  const checked = await panel
    .getByTestId("evidence-panel-checked-at")
    .textContent();
  await panel.getByRole("button", { name: "Refresh" }).click();
  await expect(panel.getByTestId("evidence-panel-checked-at")).not.toHaveText(
    checked ?? ""
  );

  // "My work doesn't show here" opens the current step's question field.
  await panel
    .getByRole("button", { name: "My work doesn't show here" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Your question on Read the scenario" })
  ).toBeFocused();
}

/** The notice and help, then a private repository refused and a public one readable. */
async function checkAccess(evidence: Locator) {
  await expect(evidence.getByTestId("notice")).toContainText(
    "an AI tool (Mistral, which may train on what it reads)"
  );
  await expect(evidence.getByTestId("notice")).toContainText(
    "keep your Evidence Project instead"
  );
  await expect(evidence.getByTestId("declare-help")).toContainText(
    "behind a login"
  );

  const url = evidence.getByRole("textbox", { name: /its address on GitHub/ });
  await url.fill("https://github.com/alan/bakery-private");
  await evidence.getByRole("button", { name: "Check access" }).click();
  await expect(evidence.getByTestId("access")).toContainText(
    "Not readable yet: grant read-only access."
  );
  await url.fill("https://github.com/alan/bakery");
  await evidence
    .getByRole("textbox", { name: /A note saying what to read/ })
    .fill("The README, then the orders pull request.");
  await evidence.getByRole("button", { name: "Check access" }).click();
  await expect(evidence.getByTestId("access")).toContainText("Readable");
}

test("an empty repository reads as a provisional reading, and GitLab is told about Reporter access", async ({
  page,
}) => {
  await signIn(page, HEDY);
  await page.goto("/competencies/C1");

  await expect(sidebar(page).getByTestId("evidence-panel-empty")).toContainText(
    "On your Evidence Project, no branch or pull request changes a file beyond the course's code (1 branch, 0 pull requests read)."
  );
  await expect(sidebar(page).getByTestId("evidence-panel-empty")).toContainText(
    "a provisional reading, not a zero"
  );

  const access = await closing(page).declare(
    "https://gitlab.com/hedy/radio",
    "The README first."
  );
  await expect(access).toContainText("give the Instructor Reporter access");
});
