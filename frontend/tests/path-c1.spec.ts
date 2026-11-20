import { expect, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import {
  answerStep,
  BAKERY,
  expectFinished,
  expectOwnGroupOnly,
  type Group,
  LINK,
  openCompetency,
  path,
  redraw,
  sendFields,
  signIn,
  step,
} from "./helpers/path";

// C1's whole Path on the Demo course (demo-course/c1.md), one Student of each
// Group: a question, a draft kept across a reload, each Locked answer and the
// Reference Drawing only after the Student's own, the optional redraw never
// waited for, the Transfer filling its point, and an Evidence Plan the Student
// edits and confirms. The roster's Students 1011 and 1012 are this file's
// alone: the in-memory Store keeps their sends while the server runs.

type Student = {
  id: number;
  group: Group;
  load: RegExp;
  change: RegExp;
  chain: string[];
  checkPoints: number;
};

const STUDENTS: Student[] = [
  {
    id: 1011,
    group: "OcéENS",
    load: /one loan every 6 seconds/,
    change: /1,200 loans an hour is one every 3 seconds/,
    chain: ["Borrow", "Loan API", "Queue", "Catalogue"],
    checkPoints: 3,
  },
  {
    id: 1012,
    group: "MATHutrice",
    load: /12,000 messages at 100 a second take 120 seconds/,
    change: /Four connections send them in 75 seconds/,
    chain: ["Issue warning", "Alert API", "Send queue", "Senders", "Gateway"],
    checkPoints: 4,
  },
];
const STEPS = [
  "read-the-scenario",
  "estimate-the-load",
  "redraw",
  "the-number-changes",
  "transfer",
  "closing",
];

for (const student of STUDENTS) {
  test(`${student.group}: C1's Path, each reference only after the Student's own`, async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await signIn(page, student.id);
    await openCompetency(page, "C1");
    await expect(page.getByTestId("time-spent")).toContainText("out of 40");
    await readAndAsk(page, student);
    await estimate(page, student);
    await redrawAndChange(page, student);
    await sendFields(step(page, "transfer"), {
      project: BAKERY,
      requirement:
        "An order is confirmed in at most 2 s, at 50 orders a minute",
    });
    await rateC1(page);
    await editAndConfirmC1(page);
    for (const id of STEPS) await expectFinished(page, id);
  });
}

/** The Group's own service, and a question folded by default. */
async function readAndAsk(page: Page, student: Student) {
  const read = step(page, "read-the-scenario");
  await expectOwnGroupOnly(read, student.group);
  const question = read.getByLabel("Your question on Read the scenario");
  await expect(question).toBeHidden();
  await read.getByText("Ask the Instructor a question").click();
  await question.fill("Is the peak always at opening time?");
  await read.getByRole("button", { name: "Send my question" }).click();
  await expect(
    read.getByRole("list", { name: "Your questions" })
  ).toContainText("Is the peak always at opening time?");
}

/** A draft survives a reload, unsent; the answer shows once the Student's own is stored. */
async function estimate(page: Page, student: Student) {
  const guided = step(page, "estimate-the-load");
  await guided.locator('[name="sentence"]').fill("___ is at most ___");
  await page.reload();
  await expect(guided.locator('[name="sentence"]')).toHaveValue(
    "___ is at most ___"
  );
  const result = await answerStep(guided, {
    sentence: "The answer is at most the promise",
    "step-1": "My calculation, step by step",
  });
  await expect(result).toContainText(student.load);
  await guided.locator('[name="step-1"]').fill("My calculation, corrected");
  await guided.getByRole("button", { name: "Send my new version" }).click();
  await expect(guided.getByTestId("sent")).toContainText("Version 2");
  await expectFinished(page, "read-the-scenario");
  await expectFinished(page, "estimate-the-load");
}

/** The redraw and its check points, one missed; then the number changes. */
async function redrawAndChange(page: Page, student: Student) {
  const checkPoints = await redraw(page, step(page, "redraw"), student.chain);
  await expect(checkPoints).toHaveCount(student.checkPoints);
  await checkPoints.nth(1).check(); // missed: the one on C1.c
  await expectFinished(page, "redraw");

  const changes = step(page, "the-number-changes");
  await expectOwnGroupOnly(changes, student.group);
  const reference = await answerStep(changes, {
    "what-moves": "The queue's load moves; the chain stays.",
  });
  await expect(reference).toContainText(student.change);

  await expect(path(page).getByTestId("path-redraw-more")).toContainText(
    "(optional)"
  );
}

/** The missed check point beside its point, the levels, the plan drafted from them. */
async function rateC1(page: Page) {
  const close = closing(page);
  await expect(close.section.getByTestId("hints-C1.c")).toBeVisible();
  await close.rate("C1.a", "I understand");
  await expect(close.plan).toHaveValue(/C1\.a \(Basic\), I understand/);
  await close.rate("C1.b", "I can redo");
  await expect(close.plan).toHaveValue(
    /carry out my Transfer, on https:\/\/github\.com\/me\/bakery/
  );
  await close.rate("C1.c", "Not yet");
  await close.rate("C1.d", "I have done it");
  await expect(close.sendSelfAssessment).toBeDisabled(); // its link first
  await close.link("C1.d", LINK);
  await expect(close.plan).not.toHaveValue(/C1\.d/);
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
}

/** The Student's text wins; a removed block leaves the levels as they are. */
async function editAndConfirmC1(page: Page) {
  const close = closing(page);
  const drafted = await close.plan.inputValue();
  const mine = drafted
    .split("\n\n")
    .filter((block) => !block.startsWith("C1.c"))
    .join("\n\n");
  await close.plan.fill(`${mine}\n\nAnd a line of my own.`);
  await close.example.fill("The README of my bakery, line 3.");
  await close.confirm.click();
  await expect(close.section.getByTestId("plan-sent")).toContainText(
    "Version 1 confirmed"
  );

  await page.reload();
  await expect(close.plan).toHaveValue(/And a line of my own\.$/);
  await expect(close.plan).not.toHaveValue(/C1\.c/);
  await expect(close.level("C1.c", "Not yet")).toBeChecked();
  await expect(path(page).getByTestId("sidebar-plan")).toContainText(
    "And a line of my own."
  );
}
