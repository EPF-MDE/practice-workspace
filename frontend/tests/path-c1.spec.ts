import { expect, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import { DRAWING_WITH_THE_MOUSE } from "./helpers/draw";
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
  test(`${student.group}: C1's Path, each reference only after the Student's own`, {
    tag: DRAWING_WITH_THE_MOUSE,
  }, async ({ page }) => {
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

async function redrawAndChange(page: Page, student: Student) {
  const checkPoints = await redraw(page, step(page, "redraw"), student.chain);
  await expect(checkPoints).toHaveCount(student.checkPoints);
  await checkPoints.nth(1).check();
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
  await expect(close.sendSelfAssessment).toBeDisabled();
  await close.link("C1.d", LINK);
  await expect(close.plan).not.toHaveValue(/C1\.d/);
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
}

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
