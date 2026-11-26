import { expect, type Locator, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import { path, signIn } from "./helpers/path";

const READS_A_BRANCH = 1041;
const READS_EMPTY = 1042;
const GRACE = 1002;

const notReadable = (repository: string) => `${repository}-private`;
const onGitHub = (repository: string) => `https://github.com/${repository}`;

const sidebar = (page: Page) => path(page).getByTestId("evidence-panel");

test("the Evidence panel says what the Reading Day would find, then the closing step declares an Evidence Project for every Competency", async ({
  page,
}) => {
  await signIn(page, READS_A_BRANCH);
  await page.goto("/competencies/C1");
  await readThePanel(page);

  const close = closing(page);
  await expect(close.section.getByTestId("evidence-panel")).toContainText(
    "feature/order-timeout"
  );
  await checkAccess(close.evidence);

  await close.rate("C1.a", "I understand");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.example.fill("The orders timeout on my bakery.");
  await close.confirm.click();
  await expect(close.section.getByTestId("plan-sent")).toContainText(
    "Version 1 confirmed"
  );
  await expect(close.evidence.getByTestId("declared")).toContainText(
    "https://github.com/alan/bakery"
  );

  const panel = sidebar(page);
  await expect(panel.getByTestId("evidence-panel-project")).toHaveText(
    "alan/bakery"
  );
  await expect(panel.getByTestId("fact-C1")).toHaveCount(0);
  await page.goto("/competencies/C2");
  await expect(sidebar(page).getByTestId("evidence-panel-project")).toHaveText(
    "alan/bakery"
  );
  await expect(closing(page).evidence.getByTestId("declared")).toContainText(
    "https://github.com/alan/bakery"
  );

  await closing(page)
    .evidence.getByRole("button", { name: /Withdraw it/ })
    .click();
  await expect(
    closing(page).evidence.getByTestId("roster-evidence-project")
  ).toBeVisible();
  await page.goto("/competencies/C1");
  await expect(sidebar(page).getByTestId("evidence-panel-project")).toHaveText(
    "alan-oceens/OceENS"
  );
  await expect(sidebar(page).getByTestId("fact-C1")).toContainText(
    "feature/order-timeout"
  );
});

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
    .getByTestId("evidence-panel-last-checked-at")
    .textContent();
  await panel.getByRole("button", { name: "Refresh" }).click();
  await expect(
    panel.getByTestId("evidence-panel-last-checked-at")
  ).not.toHaveText(checked ?? "");

  await panel
    .getByRole("button", { name: "My work doesn't show here" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Your question on Read the scenario" })
  ).toBeFocused();
}

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
  await url.fill(onGitHub(notReadable("alan/bakery")));
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

test("an empty repository reads as a provisional reading; a GitLab project and a repository the App cannot read are said as such", async ({
  page,
}) => {
  await signIn(page, READS_EMPTY);
  await page.goto("/competencies/C1");

  await expect(sidebar(page).getByTestId("evidence-panel-empty")).toContainText(
    "On your Evidence Project, no branch or pull request changes a file beyond the course's code (1 branch, 0 pull requests read)."
  );
  await expect(sidebar(page).getByTestId("evidence-panel-empty")).toContainText(
    "a provisional reading, not a zero"
  );

  const close = closing(page);
  await expect(
    await close.declare("https://gitlab.com/hedy/radio", "The README first.")
  ).toHaveAttribute("data-status", "gitlab");
  await close.rate("C1.a", "I understand");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.example.fill("The radio's README.");
  await close.confirm.click();
  await expectNotRead(sidebar(page), "hedy/radio");

  await close.declare(onGitHub(notReadable("hedy/radio")), "The README first.");
  await close.evidence
    .getByRole("button", { name: "Change my Evidence Project" })
    .click();
  await expect(
    close.evidence.getByTestId("declared").getByTestId("access")
  ).toHaveAttribute("data-status", "not-readable");
  await expectNotRead(sidebar(page), notReadable("hedy/radio"));
  await page.goto("/competencies/C3");
  await expectNotRead(sidebar(page), notReadable("hedy/radio"));
});

test("a draft of an Evidence Project kept before its note was named what to read still fills the closing step", async ({
  page,
}) => {
  await signIn(page, GRACE);
  await page.evaluate(({ key, draft }) => localStorage.setItem(key, draft), {
    key: `cws:${GRACE}:C2:evidence`,
    draft: JSON.stringify({
      url: "https://github.com/grace/compiler",
      note: "The README first.",
    }),
  });
  await page.goto("/competencies/C2");

  const close = closing(page);
  await expect(close.url).toHaveValue("https://github.com/grace/compiler");
  await expect(close.whatToRead).toHaveValue("The README first.");
});

async function expectNotRead(panel: Locator, repository: string) {
  await expect(panel.getByTestId("evidence-panel-project")).toHaveText(
    repository
  );
  await expect(panel.getByTestId("evidence-panel-unavailable")).toBeVisible();
  await expect(panel.getByTestId("evidence-panel-empty")).toHaveCount(0);
}

test("a point the Student only received from a Fallback Branch shows as received from the course, not as found", async ({
  page,
}) => {
  await signIn(page, READS_A_BRANCH);
  await page.goto("/competencies/C2");
  const panel = sidebar(page);

  await expect(panel.getByTestId("received-C2.b")).toContainText(
    "received from the course"
  );
  await expect(panel.getByTestId("received-C2.b")).toContainText(
    "Clean Bench Fallback Branch"
  );
  await expect(panel.getByTestId("received-C2.c")).toHaveCount(0);
});
