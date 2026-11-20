import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

const PORT_VARIABLE = "PRACTICE_WORKSPACE_TEST_PORT";
const isWorker = process.env.TEST_WORKER_INDEX !== undefined;

const freePort = () =>
  execFileSync(process.execPath, [
    "-e",
    'const s=require("node:net").createServer();s.listen(0,"127.0.0.1",()=>{process.stdout.write(String(s.address().port));s.close()})',
  ]).toString();

if (!isWorker || !process.env[PORT_VARIABLE]) {
  process.env[PORT_VARIABLE] = freePort();
}
const port = process.env[PORT_VARIABLE];
const baseURL = `http://127.0.0.1:${port}`;
const demoCourse = resolve(import.meta.dirname, "../demo-course");
const backend = resolve(import.meta.dirname, "../backend");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL, trace: "on-first-retry" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    cwd: backend,
    command: `uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    env: {
      WORKSPACE_CONTENT_DIR: demoCourse,
      WORKSPACE_ROSTER_FILE: resolve(demoCourse, "roster.csv"),
      WORKSPACE_SIGN_IN: "fake",
      WORKSPACE_STORE: "memory",
      WORKSPACE_REPOSITORY_READING: "fake",
      WORKSPACE_REPOSITORY_READINGS_DIR: resolve(backend, "tests/fixtures"),
      WORKSPACE_PUBLIC_URL: baseURL,
      WORKSPACE_SESSION_SECRET: "playwright",
      WORKSPACE_CLOSES_AT: "2099-01-01T00:00:00+01:00",
      WORKSPACE_READING_DAY_AT: "2099-02-01T00:00:00+01:00",
      WORKSPACE_POSTHOG_PROJECT_TOKEN: "",
      WORKSPACE_POSTHOG_HOST: "",
      WORKSPACE_POSTHOG_ENVIRONMENT: "",
    },
    url: `${baseURL}/api/health`,
    reuseExistingServer: false,
  },
});
