import { expect, type Locator, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import { path, signIn } from "./helpers/path";

// Students of the Demo roster (demo-course/roster.csv) that only this file
// signs in. The fork reading is the fake one: Alan's reading is
// backend/tests/fixtures/fork-readings/alan-oceens.json, Hedy's fork reads
// as empty. Access: a repository whose name says "private" is not readable.
const ALAN = 1041; // OcéENS, work on a branch of his fork
const HEDY = 1042; // MATHutrice, an empty fork

const sidebar = (page: Page) => path(page).getByTestId("fork-panel");

test("the fork panel says what the Reading Day would find, then the closing step declares an Evidence Project", async ({
  page,
}) => {
  await signIn(page, ALAN);
  await page.goto("/competencies/C1");
  await readThePanel(page);

  // The closing step brings the panel forward, with the Evidence Project.
  const close = closing(page);
  await expect(close.section.getByTestId("fork-panel")).toContainText(
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

  // That Competency's fork facts are greyed.
  const panel = sidebar(page);
  await expect(panel.getByTestId("fork-greyed")).toHaveText(
    "The Reading Day reads alan/bakery for C1, not your fork."
  );
  await expect(close.evidence.getByTestId("declared")).toContainText(
    "https://github.com/alan/bakery"
  );

  // Withdrawn: the fork is read again.
  await close.evidence
    .getByRole("button", { name: "Withdraw it: read my fork" })
    .click();
  await expect(close.evidence).toContainText("None declared");
  await expect(panel.getByTestId("fork-greyed")).toHaveCount(0);
});

/** Facts naming their point, when they were read, a refresh, and a way to ask. */
async function readThePanel(page: Page) {
  const panel = sidebar(page);
  await expect(panel.getByTestId("fact-C1")).toContainText(
    "feature/order-timeout changes 3 files"
  );
  await expect(panel.getByTestId("fact-C1")).toContainText("→ C1");
  await expect(panel.getByTestId("fork-not-judged")).toContainText(
    "does not judge them"
  );

  const checked = await panel.getByTestId("fork-checked-at").textContent();
  await panel.getByRole("button", { name: "Refresh" }).click();
  await expect(panel.getByTestId("fork-checked-at")).not.toHaveText(
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
    "declare your fork instead"
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

test("an empty fork reads as a provisional reading, and GitLab is told about Reporter access", async ({
  page,
}) => {
  await signIn(page, HEDY);
  await page.goto("/competencies/C1");

  await expect(sidebar(page).getByTestId("fork-empty")).toContainText(
    "On your fork, no branch or pull request changes a file beyond the course's code (1 branch, 0 pull requests read)."
  );
  await expect(sidebar(page).getByTestId("fork-empty")).toContainText(
    "a provisional reading, not a zero"
  );

  const access = await closing(page).declare(
    "https://gitlab.com/hedy/radio",
    "The README first."
  );
  await expect(access).toContainText("give the Instructor Reporter access");
});
