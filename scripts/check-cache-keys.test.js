import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { checkOn } from "./repository-with.js";

const script = join(import.meta.dirname, "check-cache-keys.js");

const workflow = (steps) => `on: workflow_dispatch
jobs:
  work:
    runs-on: ubuntu-latest
    steps:
${steps}
`;

const NPM_BOTH = `      - uses: actions/setup-node@v7.1.0
        with:
          cache: npm
          cache-dependency-path: |
            package-lock.json
            frontend/package-lock.json`;

const NPM_ROOT = `      - uses: actions/setup-node@v7.1.0
        with:
          cache: npm
          cache-dependency-path: package-lock.json`;

const UV = `      - uses: astral-sh/setup-uv@v10.3.3
        with:
          enable-cache: true
          cache-dependency-glob: backend/uv.lock`;

const chrome = (version) => `      - name: Cache agent-browser's Chrome
        uses: actions/cache@v6.1.0
        with:
          path: ~/.agent-browser/browsers
          key: agent-browser-${version}-\${{ runner.os }}`;

const WARM = workflow([NPM_BOTH, UV, chrome("0.27.0")].join("\n"));

const check = (files) => checkOn("node", script, files);

describe("check-cache-keys", () => {
  it("passes an agent workflow that reads every key warm-caches.yml writes", () => {
    const result = check({
      "warm-caches.yml": WARM,
      "agent-review.yml": workflow([NPM_BOTH, UV, chrome("0.27.0")].join("\n")),
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses an npm cache keyed on other lock files", () => {
    const result = check({
      "warm-caches.yml": WARM,
      "agent-review.yml": workflow(NPM_ROOT),
    });

    expect(result.stderr).toContain(
      'agent-review.yml: job work, step 1 reads the npm cache under "package-lock.json"'
    );
    expect(result.status).toBe(1);
  });

  it("refuses a Chrome cache under another version", () => {
    const result = check({
      "warm-caches.yml": WARM,
      "agent-implement.yml": workflow(chrome("0.28.0")),
    });

    expect(result.stderr).toContain(
      "agent-implement.yml: job work, step Cache agent-browser's Chrome reads the ~/.agent-browser/browsers cache"
    );
    expect(result.status).toBe(1);
  });

  it("refuses a cache that warm-caches.yml does not write", () => {
    const result = check({
      "warm-caches.yml": workflow(NPM_BOTH),
      "agent-explore.yml": workflow(UV),
    });

    expect(result.stderr).toContain(
      "agent-explore.yml: job work, step 1 reads the uv cache, which warm-caches.yml does not write"
    );
    expect(result.status).toBe(1);
  });
});

describe("check-cache-keys, beyond the agent workflows", () => {
  it("leaves a workflow that runs no agent alone", () => {
    const result = check({
      "warm-caches.yml": WARM,
      "check.yml": workflow(NPM_ROOT),
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses to pass without warm-caches.yml", () => {
    const result = check({ "agent-review.yml": workflow(NPM_BOTH) });

    expect(result.stderr).toContain(
      "warm-caches.yml is not among the workflows checked"
    );
    expect(result.status).toBe(1);
  });
});

describe("check-cache-keys, on the steps it reads", () => {
  it("refuses a restore-only cache under another key", () => {
    const result = check({
      "warm-caches.yml": WARM,
      "agent-review.yml": workflow(
        chrome("0.28.0").replace("actions/cache@", "actions/cache/restore@")
      ),
    });

    expect(result.stderr).toContain(
      "agent-review.yml: job work, step Cache agent-browser's Chrome reads the ~/.agent-browser/browsers cache"
    );
    expect(result.status).toBe(1);
  });
});
