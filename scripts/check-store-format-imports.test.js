import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { checkOn } from "./repository-with.js";

const script = join(import.meta.dirname, "check-store-format-imports.py");

const checkTests = (files) => checkOn("python3", script, files);

describe("check-store-format-imports", () => {
  it("passes a test importing the Store itself", () => {
    const result = checkTests({
      "backend/tests/test_answers.py":
        "from app.store import GitHubStore, InMemoryStore, Store\n",
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("passes the Store's contract suite importing the stored format", () => {
    const result = checkTests({
      "backend/tests/store_contract/test_sends.py":
        "from app.store import Entry, Kind, Store\n",
    });

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses a test outside the contract suite importing the stored format", () => {
    const result = checkTests({
      "backend/tests/test_answers.py":
        "from app.store import InMemoryStore, Kind\n",
    });

    expect(result.stderr).toContain(
      "backend/tests/test_answers.py:1: imports app.store.Kind"
    );
    expect(result.status).toBe(1);
  });

  it("refuses a test importing the Store's internals or the whole module", () => {
    const result = checkTests({
      "backend/tests/test_answers.py": `import app.store._internal.comments
from app import store
`,
    });

    expect(result.stderr).toContain(
      "test_answers.py:1: imports app.store._internal.comments"
    );
    expect(result.stderr).toContain("test_answers.py:2: imports app.store");
    expect(result.status).toBe(1);
  });
});
