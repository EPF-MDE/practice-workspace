import { execFileSync, spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { localInstance } from "../frontend/instance.ts";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const demoCourse = resolve(root, "demo-course");
const out = resolve(root, process.argv[2] ?? "docs/screenshots");
const session = `screenshots-${process.pid}`;
const ADA = 1001;

const freePort = () =>
  new Promise((done) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => done(port));
    });
  });

const browser = (...args) =>
  execFileSync("npx", ["agent-browser", "--session", session, ...args], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });

const startDemoCourse = (port) => {
  const { baseURL, cwd, command, env } = localInstance(
    demoCourse,
    String(port),
    "screenshots"
  );
  const [program, ...args] = command;
  const server = spawn(program, args, {
    cwd,
    stdio: ["ignore", "ignore", "inherit"],
    env: { ...process.env, ...env },
  });
  return { baseURL, server };
};

const healthy = async (baseURL) => {
  for (let attempt = 0; attempt < 120; attempt++) {
    try {
      if ((await fetch(`${baseURL}/api/health`)).ok) return;
    } catch {}
    await new Promise((wait) => setTimeout(wait, 500));
  }
  throw new Error(`The Demo course did not answer on ${baseURL}`);
};

const scrollTo = (selector) =>
  browser(
    "eval",
    `document.querySelector(${JSON.stringify(selector)}).scrollIntoView()`
  );

const press = (section, button) =>
  browser(
    "eval",
    `[...document.querySelectorAll(${JSON.stringify(`${section} button`)})]
      .find((b) => b.textContent.trim() === ${JSON.stringify(button)})
      .click()`
  );

const box = (selector) =>
  JSON.parse(
    JSON.parse(
      browser(
        "eval",
        `JSON.stringify(document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect())`
      )
    )
  );

const drag = (from, to) => {
  browser("mouse", "move", String(from.x), String(from.y));
  browser("mouse", "down");
  browser("mouse", "move", String(to.x), String(to.y), "--steps", "8");
  browser("mouse", "up");
};

const drawChain = (canvasSelector, labels) => {
  browser("eval", "document.activeElement?.blur()");
  browser("scrollintoview", canvasSelector);
  const canvas = box(canvasSelector);
  const empty = { x: canvas.x + canvas.width / 2, y: canvas.bottom - 60 };
  drag(empty, empty);
  const centres = labels.map((label, index) => {
    const at = { x: canvas.x + 40 + index * 185, y: canvas.y + 120 };
    browser("press", "Escape");
    browser("press", "r");
    drag(at, { x: at.x + 140, y: at.y + 80 });
    browser("press", "Enter");
    browser("keyboard", "inserttext", label);
    browser("press", "Escape");
    browser("press", "Escape");
    return { x: at.x + 70, y: at.y + 40 };
  });
  centres.slice(1).forEach((centre, index) => {
    browser("press", "a");
    drag(centres[index], centre);
    browser("press", "Escape");
  });
};

const shoot = (name) => {
  browser("wait", "500");
  browser("screenshot", resolve(out, `${name}.png`));
  console.log(`saved ${resolve(out, `${name}.png`)}`);
};

const walkThePath = (baseURL) => {
  browser("set", "viewport", "1280", "860");
  browser("open", `${baseURL}/auth/login?github_id=${ADA}`);
  browser("wait", "--text", "Your path");
  shoot("1-workspace");

  browser("open", `${baseURL}/competencies/C1`);
  browser("wait", "section#read-the-scenario img");
  shoot("2-path");

  const estimate = "section#estimate-the-load";
  press("section#read-the-scenario", "I have read this");
  browser(
    "fill",
    `${estimate} [name="sentence"]`,
    "A reader's answer is at most 5 seconds away"
  );
  browser(
    "fill",
    `${estimate} [name="step-1"]`,
    "One loan every 6 seconds; the catalogue is busy a third of the time."
  );
  press(estimate, "Send my answer");
  browser("wait", `${estimate} [data-testid="answer"]`);
  scrollTo(estimate);
  shoot("3-answer-after-your-own");

  browser("wait", 'section#redraw [data-testid="canvas"]');
  scrollTo("section#redraw");
  browser("wait", "section#redraw .tl-shape");
  shoot("4-drawing");

  const redraw = "section#redraw";
  drawChain(`${redraw} figure[aria-label="Your drawing"] .tl-canvas`, [
    "Borrow",
    "Loan API",
    "Queue",
    "Catalogue",
  ]);
  press(redraw, "Send my drawing");
  browser("wait", `${redraw} [data-testid="reference-drawing"]`);

  const change = "section#the-number-changes";
  browser(
    "fill",
    `${change} [name="what-moves"]`,
    "The queue's load doubles; a second catalogue worker joins it."
  );
  press(change, "Send my answer");
  browser("wait", `${change} [data-testid="answer"]`);

  scrollTo("section#closing");
  shoot("5-self-assessment");
};

mkdirSync(out, { recursive: true });
execFileSync("npm", ["--prefix", "frontend", "run", "--silent", "build"], {
  cwd: root,
  stdio: "inherit",
});
const { baseURL, server } = startDemoCourse(await freePort());
try {
  await healthy(baseURL);
  walkThePath(baseURL);
} finally {
  try {
    browser("close");
  } finally {
    server.kill();
  }
}
