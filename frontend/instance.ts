import { resolve } from "node:path";

const backend = resolve(import.meta.dirname, "../backend");

export function localInstance(
  courseFolder: string,
  port: string,
  sessionSecret: string
) {
  const baseURL = `http://127.0.0.1:${port}`;
  return {
    baseURL,
    cwd: backend,
    command: [
      "uv",
      "run",
      "--frozen",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      port,
    ],
    env: {
      WORKSPACE_COURSE_FOLDER: courseFolder,
      WORKSPACE_ROSTER_FILE: resolve(courseFolder, "roster.csv"),
      WORKSPACE_SIGN_IN: "fake",
      WORKSPACE_STORE: "memory",
      WORKSPACE_REPOSITORY_READING: "fake",
      WORKSPACE_REPOSITORY_READINGS_DIR: resolve(backend, "tests/fixtures"),
      WORKSPACE_PUBLIC_URL: baseURL,
      WORKSPACE_SESSION_SECRET: sessionSecret,
      WORKSPACE_POSTHOG_PROJECT_TOKEN: "",
      WORKSPACE_POSTHOG_HOST: "",
      WORKSPACE_POSTHOG_ENVIRONMENT: "",
    },
  };
}
