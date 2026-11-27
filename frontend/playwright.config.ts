import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { demoCourse, localInstance } from "./instance.ts";
import { DRAWING_WITH_THE_MOUSE } from "./tests/helpers/draw";

const isWorker = process.env.TEST_WORKER_INDEX !== undefined;

const freePort = () =>
  execFileSync(process.execPath, [
    "-e",
    'const s=require("node:net").createServer();s.listen(0,"127.0.0.1",()=>{process.stdout.write(String(s.address().port));s.close()})',
  ]).toString();

const portFor = (variable: string) => {
  if (!isWorker || !process.env[variable]) {
    process.env[variable] = freePort();
  }
  return process.env[variable];
};

const readingNothing = resolve(
  import.meta.dirname,
  "../backend/tests/fixtures/courses/reads-nothing"
);
const READS_NOTHING = /reads-nothing\.spec\.ts/;
const DRAWS_WITH_THE_MOUSE = new RegExp(DRAWING_WITH_THE_MOUSE);
const DRAWING_TEST_TIMEOUT = 120_000;

const instance = (courseFolder: string, portVariable: string) => {
  const { baseURL, cwd, command, env } = localInstance(
    courseFolder,
    portFor(portVariable),
    "playwright"
  );
  return {
    baseURL,
    webServer: {
      cwd,
      command: command.join(" "),
      env,
      url: `${baseURL}/api/health`,
      reuseExistingServer: false,
    },
  };
};

const demo = instance(demoCourse, "PRACTICE_WORKSPACE_TEST_PORT");
const nothing = instance(
  readingNothing,
  "PRACTICE_WORKSPACE_READS_NOTHING_TEST_PORT"
);

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { trace: "on-first-retry" },
  projects: [
    {
      name: "chromium",
      testIgnore: READS_NOTHING,
      grepInvert: DRAWS_WITH_THE_MOUSE,
      use: { ...devices["Desktop Chrome"], baseURL: demo.baseURL },
    },
    {
      name: "chromium, drawing with the mouse",
      testIgnore: READS_NOTHING,
      grep: DRAWS_WITH_THE_MOUSE,
      timeout: DRAWING_TEST_TIMEOUT,
      use: { ...devices["Desktop Chrome"], baseURL: demo.baseURL },
    },
    {
      name: "chromium, a Course reading nothing when none is declared",
      testMatch: READS_NOTHING,
      use: { ...devices["Desktop Chrome"], baseURL: nothing.baseURL },
    },
  ],
  webServer: [demo.webServer, nothing.webServer],
});
