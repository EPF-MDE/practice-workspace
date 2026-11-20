import { expect, type Page, test } from "@playwright/test";
import { drawChain } from "./helpers/draw";
import { path, signIn, step } from "./helpers/path";

const STUDENTS = [
  { id: 1021, group: "OcéENS", checkPoints: 3 },
  { id: 1022, group: "MATHutrice", checkPoints: 4 },
];
const CHAIN = ["Start", "Front door", "Queue", "Worker", "Store", "Reply"];
const SHAPES = CHAIN.length * 2 - 1;

for (const student of STUDENTS) {
  test(`${student.group}: the redraw is kept while drawing, sent, then compared with the Reference Drawing`, async ({
    page,
    browser,
  }, testInfo) => {
    test.setTimeout(90_000);
    await signIn(page, student.id);
    await page.goto("/competencies/C1");
    await drawAndReload(page);

    const redraw = step(page, "redraw");
    const [response] = await Promise.all([
      page.waitForResponse(
        (answer) =>
          answer.url().endsWith("/steps/redraw/drawing") &&
          answer.request().method() === "POST"
      ),
      redraw.getByRole("button", { name: "Send my drawing" }).click(),
    ]);
    const sent = await response.json();
    expect(sent.reference.check_points).toHaveLength(student.checkPoints);
    testInfo.annotations.push({
      type: "drawing sizes",
      description: `${CHAIN.length} boxes, ${CHAIN.length - 1} arrows: PNG ${sent.png_bytes} bytes, snapshot ${sent.snapshot_bytes} bytes`,
    });
    await compare(page, student.checkPoints);

    const other = await browser.newContext();
    const elsewhere = await other.newPage();
    await signIn(elsewhere, student.id);
    await elsewhere.goto("/competencies/C1");
    await expect(
      step(elsewhere, "redraw")
        .getByRole("figure", { name: "Your drawing" })
        .locator(".tl-shape")
    ).toHaveCount(SHAPES);
    await other.close();
  });
}

async function drawAndReload(page: Page) {
  const redraw = step(page, "redraw");
  const example = redraw.getByRole("figure", { name: "Example Drawing" });
  await expect(example.locator(".tl-shape").first()).toBeVisible();
  await expect(redraw.getByTestId("reference-locked")).toBeVisible();
  await expect(redraw.getByTestId("reference-drawing")).toHaveCount(0);

  const canvas = redraw.getByRole("figure", { name: "Your drawing" });
  await drawChain(page, canvas.locator(".tl-canvas"), CHAIN);
  const shapes = canvas.locator(".tl-shape");
  await expect(shapes).toHaveCount(SHAPES);
  await expect(canvas.getByText("Worker")).toBeVisible();
  await page.waitForTimeout(500);
  await page.reload();
  await expect(shapes).toHaveCount(SHAPES);
  await expect(redraw.getByTestId("reference-locked")).toBeVisible();
}

async function compare(page: Page, checkPoints: number) {
  const redraw = step(page, "redraw");
  const reference = redraw.getByTestId("reference-drawing");
  await expect(
    reference
      .getByRole("figure", { name: "Reference Drawing" })
      .locator(".tl-shape")
      .first()
  ).toBeVisible();
  await expect(redraw.getByTestId("drawing-sent")).toContainText("Version 1");
  await expect(path(page).getByTestId("path-redraw")).toHaveAttribute(
    "data-finished",
    "true"
  );

  const boxes = reference.getByRole("checkbox");
  await expect(boxes).toHaveCount(checkPoints);
  await boxes.first().check();
  await page.reload();
  await expect(boxes.first()).toBeChecked();
  await expect(boxes.nth(1)).not.toBeChecked();

  await redraw.getByRole("button", { name: "Send my new version" }).click();
  await expect(redraw.getByTestId("drawing-sent")).toContainText("Version 2");
}
