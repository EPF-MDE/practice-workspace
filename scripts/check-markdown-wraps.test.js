import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(import.meta.dirname, "check-markdown-wraps.js");

const checkMarkdown = (contents) => {
  const root = mkdtempSync(join(tmpdir(), "check-markdown-wraps-"));
  writeFileSync(join(root, "doc.md"), contents);
  return spawnSync("node", [script, "doc.md"], { cwd: root, encoding: "utf8" });
};

const CLEAN = `---
title: front matter
lines: two
---

# A heading
A paragraph right under its heading.

- A list item.
  - A nested list item.
1. A numbered item.

> A quote.

| A | table |
| - | ----- |
| B | row   |

\`\`\`text
code keeps
its lines
\`\`\`

    indented code
    keeps its lines

A line ends on a deliberate break,\\
and one on two spaces,  
as Markdown allows.

A | table
--|------
without | leading pipes

::: field {#sentence kind=line}
A directive's text.
:::

<!--
a comment keeps
its lines
-->
`;

describe("check-markdown-wraps", () => {
  it("passes paragraphs, list items and blocks each on their own lines", () => {
    const result = checkMarkdown(CLEAN);

    expect(result.stderr).toBe("");
    expect(result.status).toBe(0);
  });

  it("refuses a hard-wrapped paragraph", () => {
    const result = checkMarkdown(
      "A paragraph that goes\non after a line break.\n"
    );

    expect(result.stderr).toContain("doc.md:2: on after a line break.");
    expect(result.status).toBe(1);
  });

  it("refuses a hard-wrapped paragraph after code naming its fence", () => {
    const result = checkMarkdown(
      "```\nnaming ``` inside\n```\nA paragraph that goes\non after a line break.\n"
    );

    expect(result.stderr).toContain("doc.md:5: on after a line break.");
    expect(result.status).toBe(1);
  });

  it("refuses a hard-wrapped list item", () => {
    const result = checkMarkdown(
      "- A list item that goes\n  on after a line break.\n"
    );

    expect(result.stderr).toContain("doc.md:2: on after a line break.");
    expect(result.status).toBe(1);
  });

  it("refuses a hard-wrapped quote", () => {
    const result = checkMarkdown(
      "> A quote that goes\n> on after a line break.\n"
    );

    expect(result.stderr).toContain("doc.md:2: > on after a line break.");
    expect(result.status).toBe(1);
  });
});
