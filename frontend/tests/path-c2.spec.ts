import { expect, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import {
  answerStep,
  BAKERY,
  choose,
  expectFinished,
  expectOwnGroupOnly,
  type Group,
  openCompetency,
  send,
  sendFields,
  signIn,
  step,
} from "./helpers/path";

type Student = {
  id: number;
  group: Group;
  picks: Record<string, string>;
  explained: string;
};

const FAILS = "Change 2: which job fails?";
const STUDENTS: Student[] = [
  {
    id: 1031,
    group: "Willow",
    picks: {
      "Change 1: which job fails?": "lint",
      "Change 1: can its pull request merge?": "no",
      [FAILS]: "test",
      "Change 2: can its pull request merge?": "no",
    },
    explained: "still expects 14 days",
  },
  {
    id: 1032,
    group: "Cedar",
    picks: {
      "Change 1: which job fails?": "lint",
      "Change 1: can its pull request merge?": "yes",
      [FAILS]: "deploy",
      "Change 2: can its pull request merge?": "yes",
    },
    explained: "never reaches production",
  },
];

for (const student of STUDENTS) {
  test(`${student.group}: C2's Path, a Check explained only once sent, a GitLab Evidence Project`, async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await signIn(page, student.id);
    await openCompetency(page, "C2");
    await expectOwnGroupOnly(step(page, "read-the-pipeline"), student.group);
    await check(page, student);
    const gate = await answerStep(step(page, "what-the-gate-misses"), {
      sentence: "A page no test opens; a test that opens it would catch it.",
    });
    await expect(gate).toContainText("only sees what a job checks");
    await sendFields(step(page, "transfer"), {
      project: BAKERY,
      change: "Rename the price field the order test reads",
      check: "test",
    });
    await closeC2(page);
  });
}

async function check(page: Page, student: Student) {
  const predict = step(page, "predict-the-pipeline");
  await expectOwnGroupOnly(predict, student.group);
  await expect(predict.getByTestId("answer-locked")).toBeVisible();
  await expect(predict.getByTestId("answer")).toHaveCount(0);
  const pick = student.picks[FAILS] ?? "";
  await choose(predict, FAILS, pick);
  await page.reload();
  await expect(
    predict
      .getByRole("radiogroup", { name: FAILS })
      .getByRole("radio", { name: pick, exact: true })
  ).toBeChecked();
  await expect(predict.getByTestId("answer-locked")).toBeVisible();
  for (const [label, option] of Object.entries(student.picks)) {
    await choose(predict, label, option);
  }
  await send(predict);
  const answer = predict.getByTestId("answer");
  await expect(answer).toContainText("The Instructor's answer");
  await expect(answer.getByRole("table")).toContainText(student.explained);
  await expectFinished(page, "predict-the-pipeline");
}

async function closeC2(page: Page) {
  const close = closing(page);
  await close.rate("C2.a", "I can redo");
  await expect(close.plan).toHaveValue(
    /my Transfer, on https:\/\/github\.com\/me\/bakery/
  );
  await close.rate("C2.b", "I understand");
  await expect(close.plan).toHaveValue(/C2\.b \(Solid\), I understand/);
  await close.rate("C2.c", "Not yet");
  await expect(
    await close.declare(
      "https://gitlab.com/me/bakery",
      "The pipeline file, then the red merge request."
    )
  ).toContainText("give the Instructor Reporter access");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.plan.fill(
    `${await close.plan.inputValue()}\n\nAsk a classmate to break my pipeline.`
  );
  await close.example.fill("The red pull request of my bakery.");
  await close.confirm.click();
  await expect(close.section.getByTestId("plan-sent")).toContainText(
    "Version 1 confirmed"
  );
  await expect(close.evidence.getByTestId("declared")).toContainText(
    "https://gitlab.com/me/bakery"
  );
  await expectFinished(page, "closing");
}
