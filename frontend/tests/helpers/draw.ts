import type { Locator, Page } from "@playwright/test";

/**
 * Draws a chain on a tldraw canvas as a Student would, with the mouse and
 * tldraw's keyboard shortcuts: one labelled box per step, in rows of three,
 * and an arrow from each box to the next.
 *
 * Positions are in the canvas's own coordinates, turned into the page's
 * before each gesture: the page may scroll while a label is edited.
 */

type Point = { x: number; y: number };

const WIDTH = 150;
const HEIGHT = 80;
const GAP_X = 50;
const GAP_Y = 70;
const PER_ROW = 3;

/** A point of the canvas, in the page's coordinates. */
async function onPage(canvas: Locator, at: Point): Promise<Point> {
  const box = await canvas.boundingBox();
  if (!box) throw new Error("no canvas on the page");
  return { x: box.x + at.x, y: box.y + at.y };
}

async function drag(page: Page, canvas: Locator, line: [Point, Point]) {
  const start = await onPage(canvas, line[0]);
  const end = await onPage(canvas, line[1]);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move((start.x + end.x) / 2, (start.y + end.y) / 2, {
    steps: 4,
  });
  await page.mouse.move(end.x, end.y, { steps: 4 });
  await page.mouse.up();
}

/** Draws one labelled box with its top-left corner at `box`. */
async function drawBox(
  page: Page,
  canvas: Locator,
  box: Point & { label: string }
) {
  const size = await canvas.boundingBox();
  if (!size) throw new Error("no canvas on the page");
  // An empty spot below the drawing, clear of tldraw's panels: focus, nothing selected.
  const empty = await onPage(canvas, {
    x: size.width / 2,
    y: size.height - 110,
  });
  await page.mouse.click(empty.x, empty.y);
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await drag(page, canvas, [box, { x: box.x + WIDTH, y: box.y + HEIGHT }]);
  await page.keyboard.press("Enter"); // edit the new box's label
  await page.keyboard.insertText(box.label); // no key events: no shortcut fires
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
}

export async function drawChain(page: Page, canvas: Locator, labels: string[]) {
  await canvas.scrollIntoViewIfNeeded();
  const centres: Point[] = [];
  for (const [index, label] of labels.entries()) {
    const x = 30 + (index % PER_ROW) * (WIDTH + GAP_X);
    const y = 70 + Math.floor(index / PER_ROW) * (HEIGHT + GAP_Y);
    await drawBox(page, canvas, { x, y, label });
    centres.push({ x: x + WIDTH / 2, y: y + HEIGHT / 2 });
  }
  for (const [index, centre] of centres.entries()) {
    const previous = centres[index - 1];
    if (!previous) continue;
    await page.keyboard.press("a");
    await drag(page, canvas, [previous, centre]);
    await page.keyboard.press("Escape");
  }
}
