import { expect, type Locator, type Page } from "@playwright/test";

export const DRAWING_WITH_THE_MOUSE = "@drawing-with-the-mouse";

type Point = { x: number; y: number };
type Rect = Point & { width: number; height: number };

export type Hand = {
  canvas(): Promise<Rect>;
  move(to: Point, steps: number): Promise<void>;
  down(): Promise<void>;
  up(): Promise<void>;
  press(key: string): Promise<void>;
  insertText(text: string): Promise<void>;
};

const WIDTH = 150;
const HEIGHT = 80;
const GAP_X = 50;
const GAP_Y = 70;
const PER_ROW = 3;

async function onPage(hand: Hand, at: Point): Promise<Point> {
  const box = await hand.canvas();
  return { x: box.x + at.x, y: box.y + at.y };
}

async function drag(hand: Hand, line: [Point, Point]) {
  const start = await onPage(hand, line[0]);
  const end = await onPage(hand, line[1]);
  await hand.move(start, 1);
  await hand.down();
  await hand.move({ x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 }, 4);
  await hand.move(end, 4);
  await hand.up();
}

async function drawBox(hand: Hand, box: Point & { label: string }) {
  const size = await hand.canvas();
  const empty = { x: size.width / 2, y: size.height - 110 };
  await drag(hand, [empty, empty]);
  await hand.press("Escape");
  await hand.press("r");
  await drag(hand, [box, { x: box.x + WIDTH, y: box.y + HEIGHT }]);
  await hand.press("Enter");
  await hand.insertText(box.label);
  await hand.press("Escape");
  await hand.press("Escape");
}

export function shapesOfChain(labels: string[]): number {
  return labels.length * 2 - 1;
}

export async function drawChainWith(hand: Hand, labels: string[]) {
  const centres: Point[] = [];
  for (const [index, label] of labels.entries()) {
    const x = 30 + (index % PER_ROW) * (WIDTH + GAP_X);
    const y = 70 + Math.floor(index / PER_ROW) * (HEIGHT + GAP_Y);
    await drawBox(hand, { x, y, label });
    centres.push({ x: x + WIDTH / 2, y: y + HEIGHT / 2 });
  }
  for (const [index, centre] of centres.entries()) {
    const previous = centres[index - 1];
    if (!previous) continue;
    await hand.press("a");
    await drag(hand, [previous, centre]);
    await hand.press("Escape");
  }
}

export async function drawChain(page: Page, canvas: Locator, labels: string[]) {
  await canvas.scrollIntoViewIfNeeded();
  await drawChainWith(
    {
      canvas: async () => {
        const box = await canvas.boundingBox();
        if (!box) throw new Error("no canvas on the page");
        return box;
      },
      move: (to, steps) => page.mouse.move(to.x, to.y, { steps }),
      down: () => page.mouse.down(),
      up: () => page.mouse.up(),
      press: (key) => page.keyboard.press(key),
      insertText: (text) => page.keyboard.insertText(text),
    },
    labels
  );
}

type KeptDrawing = { shapes: number; labels: string[] };
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
    ) as { typeName?: string; props?: unknown }[];
    const shapes = records.filter((record) => record.typeName === "shape");
    const textIn = (node: unknown): string => {
      if (Array.isArray(node)) return node.map(textIn).join("");
      if (typeof node !== "object" || node === null) return "";
      if ("text" in node && typeof node.text === "string") return node.text;
      return "content" in node ? textIn(node.content) : "";
    };
    return {
      shapes: shapes.length,
      labels: shapes
        .map((shape) =>
          textIn((shape.props as { richText?: unknown })?.richText)
        )
        .filter((label) => label !== ""),
    };
  }, `:${competency}:drawing:${step}`);
}

export async function expectChainKept(
  page: Page,
  drawing: DrawingStep,
  labels: string[]
) {
  await expect
    .poll(async () => {
      const kept = await keptDrawing(page, drawing);
      return kept === null
        ? null
        : { shapes: kept.shapes, labels: [...kept.labels].sort() };
    })
    .toEqual({ shapes: shapesOfChain(labels), labels: [...labels].sort() });
}
