import { execFileSync, spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(root, "backend");
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

const startDemoCourse = (port, baseURL) =>
  spawn(
    "uv",
    [
      "run",
      "--frozen",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      cwd: backend,
      stdio: ["ignore", "ignore", "inherit"],
      env: {
        ...process.env,
        WORKSPACE_COURSE_FOLDER: demoCourse,
        WORKSPACE_ROSTER_FILE: resolve(demoCourse, "roster.csv"),
        WORKSPACE_SIGN_IN: "fake",
        WORKSPACE_STORE: "memory",
        WORKSPACE_REPOSITORY_READING: "fake",
        WORKSPACE_REPOSITORY_READINGS_DIR: resolve(backend, "tests/fixtures"),
        WORKSPACE_PUBLIC_URL: baseURL,
        WORKSPACE_SESSION_SECRET: "screenshots",
        WORKSPACE_POSTHOG_PROJECT_TOKEN: "",
        WORKSPACE_POSTHOG_HOST: "",
        WORKSPACE_POSTHOG_ENVIRONMENT: "",
      },
    }
  );

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

  scrollTo("section#closing");
  shoot("5-self-assessment");
};

mkdirSync(out, { recursive: true });
execFileSync("npm", ["--prefix", "frontend", "run", "--silent", "build"], {
  cwd: root,
  stdio: "inherit",
});
const port = await freePort();
const baseURL = `http://127.0.0.1:${port}`;
const server = startDemoCourse(port, baseURL);
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
