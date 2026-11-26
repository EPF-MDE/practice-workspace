import { expect, type Locator, type Page } from "@playwright/test";

export const DRAWING_TEST_TIMEOUT = 120_000;

type Point = { x: number; y: number };

const WIDTH = 150;
const HEIGHT = 80;
const GAP_X = 50;
const GAP_Y = 70;
const PER_ROW = 3;

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

async function drawBox(
  page: Page,
  canvas: Locator,
  box: Point & { label: string }
) {
  const size = await canvas.boundingBox();
  if (!size) throw new Error("no canvas on the page");
  const empty = await onPage(canvas, {
    x: size.width / 2,
    y: size.height - 110,
  });
  await page.mouse.click(empty.x, empty.y);
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await drag(page, canvas, [box, { x: box.x + WIDTH, y: box.y + HEIGHT }]);
  await page.keyboard.press("Enter");
  await page.keyboard.insertText(box.label);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
}

export function shapesOfChain(labels: string[]): number {
  return labels.length * 2 - 1;
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

type KeptDrawing = { shapes: number; text: string };
type DrawingStep = { competency: string; step: string };

async function keptDrawing(
  page: Page,
  { competency, step }: DrawingStep
): Promise<KeptDrawing | null> {
  return page.evaluate((suffix) => {
    const name = Object.keys(localStorage).find((key) => key.endsWith(suffix));
    const text = name === undefined ? null : localStorage.getItem(name);
    if (text === null) return null;
    const records = Object.values(
      (JSON.parse(text) as { document?: { store?: object } }).document?.store ??
        {}
    ) as { typeName?: string }[];
    const shapes = records.filter((record) => record.typeName === "shape");
    return { shapes: shapes.length, text };
  }, `:${competency}:drawing:${step}`);
}

export async function expectChainKept(
  page: Page,
  where: DrawingStep,
  labels: string[]
) {
  await expect
    .poll(async () => {
      const kept = await keptDrawing(page, where);
      return (
        kept !== null &&
        kept.shapes === shapesOfChain(labels) &&
        labels.every((label) => kept.text.includes(label))
      );
    })
    .toBe(true);
}
