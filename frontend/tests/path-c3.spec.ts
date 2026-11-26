import { expect, type Page, test } from "@playwright/test";
import { closing } from "./helpers/closing";
import {
  answerStep,
  BAKERY,
  choose,
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
  stepOrder,
} from "./helpers/path";

type Student = {
  id: number;
  group: Group;
  later: string;
  ranking: string;
  notes: string;
  checkPoints: number;
  whyFirst: string;
};

const STUDENTS: Student[] = [
  {
    id: 1051,
    group: "OcéENS",
    later: "X",
    ranking: "Z, then X, then Y",
    notes: "https://example.com/demo/lendly-ranking",
    checkPoints: 3,
    whyFirst: "Why Z before X",
  },
  {
    id: 1052,
    group: "MATHutrice",
    later: "Q",
    ranking: "P, then Q, then R",
    notes: "https://example.com/demo/skywatch-ranking",
    checkPoints: 4,
    whyFirst: "Why P before Q",
  },
];
const STEPS = [
  "read-the-errors",
  "rank-the-errors",
  "redraw",
  "follow-the-fix",
  "transfer",
  "closing",
];

for (const student of STUDENTS) {
  test(`${student.group}: C3's Path, a step waiting for the ranking, a GitHub Evidence Project`, {
    tag: "@drawing-with-the-mouse",
  }, async ({ page }) => {
    await signIn(page, student.id);
    await openCompetency(page, "C3");
    await expect(step(page, "read-the-errors")).toContainText("Pantry");
    const order = await stepOrder(page);
    expect(order.indexOf("redraw")).toBeGreaterThan(
      order.indexOf("rank-the-errors")
    );
    await expectWaiting(page);
    await rank(page, student);
    const checkPoints = await redraw(page, step(page, "redraw"), [
      "Error",
      "Error tracking",
      "Ranking",
    ]);
    await expect(checkPoints).toHaveCount(student.checkPoints);
    await checkPoints.last().check();
    await followTheFix(page, student);
    await sendFields(step(page, "transfer"), {
      project: BAKERY,
      error: "A payment that times out, for every customer paying",
      signal: "The exception in the error tracking",
    });
    await closeC3(page);
    for (const id of STEPS) await expectFinished(page, id);
  });
}

async function expectWaiting(page: Page) {
  const waiting = step(page, "follow-the-fix");
  await expect(waiting).toContainText("Pantry's fix");
  await expect(waiting.getByTestId("waiting")).toContainText(
    "Send your ranking first"
  );
  await expect(waiting.locator("input[name], textarea[name]")).toHaveCount(0);
  await expect(
    waiting.getByRole("button", { name: "Send my answer" })
  ).toHaveCount(0);
  await expect(waiting).not.toContainText("Why fix");
  await expect(path(page).getByTestId("path-follow-the-fix")).toContainText(
    "(after Rank the errors)"
  );
}

async function rank(page: Page, student: Student) {
  const section = step(page, "rank-the-errors");
  await expectOwnGroupOnly(section, student.group);
  await choose(
    section,
    "Which error would you watch next week?",
    student.later
  );
  const answer = await answerStep(section, {
    ranking: "The one that loses something, first",
    why: "Harm to each person before the count.",
  });
  await expect(answer).toContainText(student.ranking);
  await expect(answer.locator(`a[href="${student.notes}"]`)).toBeVisible();
}

async function followTheFix(page: Page, student: Student) {
  const fix = step(page, "follow-the-fix");
  await expect(fix).toContainText("Pantry's fix");
  await expect(fix.getByTestId("waiting")).toHaveCount(0);
  await expect(path(page).getByTestId("path-follow-the-fix")).not.toContainText(
    "(after"
  );
  const followed = await answerStep(fix, {
    after: "The error shows 0 times.",
    "why-first": "It harmed each person it reached.",
  });
  await expect(followed).toContainText(student.whyFirst);
}

async function closeC3(page: Page) {
  const close = closing(page);
  await expect(close.section.getByTestId("hints-C3.c")).toBeVisible();
  await close.rate("C3.a", "I understand");
  await expect(close.plan).toHaveValue(/C3\.a \(Basic\), I understand/);
  await close.rate("C3.c", "I can redo");
  await expect(close.plan).toHaveValue(
    /my Transfer, on https:\/\/github\.com\/me\/bakery/
  );
  await close.rate("C3.b", "I have done it");
  await close.link("C3.b", LINK);
  await expect(
    await close.declare(BAKERY, "The error tracking issue, then its fix.")
  ).toHaveAttribute("data-status", "readable");
  await close.sendSelfAssessment.click();
  await expect(close.section.getByTestId("sa-sent")).toContainText("Version 1");
  await close.example.fill("My bakery's payment error, ranked on its harm.");
  await close.confirm.click();
  await expect(close.section.getByTestId("plan-sent")).toContainText(
    "Version 1 confirmed"
  );
  await expect(close.evidence.getByTestId("declared")).toContainText(BAKERY);
}
