import { readFileSync } from "node:fs";

const FENCE = /^(`{3,}|~{3,})/;
const HEADING = /^#{1,6}(\s|$)/;
const TABLE_ROW = /^\|/;
const HTML = /^</;
const DIRECTIVE = /^:::/;
const RULE = /^([-*_=])(\s*\1){2,}\s*$/;
const LIST_ITEM = /^([-*+]|\d+[.)])\s/;
const QUOTE = /^>/;
const LINK_DEFINITION = /^\[[^\]]+\]:\s/;

const HOLDS_NO_PROSE = [HEADING, TABLE_ROW, HTML, DIRECTIVE, RULE];
const STARTS_A_BLOCK = [...HOLDS_NO_PROSE, LIST_ITEM, QUOTE, LINK_DEFINITION];

const matchesAny = (patterns, text) =>
  patterns.some((pattern) => pattern.test(text));

const NOTHING = { prose: false, quoted: false };

const wrapsIn = (file) => {
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  const found = [];
  let skipUntil = lines[0] === "---" ? "---" : null;
  let previous = NOTHING;

  lines.forEach((line, index) => {
    const text = line.trim();
    if (skipUntil !== null) {
      if (index > 0 && text.includes(skipUntil)) skipUntil = null;
      return;
    }
    const fence = text.match(FENCE);
    if (fence || text.startsWith("<!--")) {
      skipUntil = fence ? fence[1] : "-->";
      if (!fence && text.includes("-->")) skipUntil = null;
      previous = NOTHING;
      return;
    }
    const quoted = QUOTE.test(text);
    const content = text.replace(/^(>\s?)+/, "");
    if (content === "") {
      previous = NOTHING;
      return;
    }
    const continues =
      previous.prose &&
      previous.quoted === quoted &&
      !matchesAny(STARTS_A_BLOCK, quoted ? content : text);
    if (continues) {
      found.push(`${file}:${index + 1}: ${text.slice(0, 60)}`);
    }
    previous = { prose: !matchesAny(HOLDS_NO_PROSE, content), quoted };
  });
  return found;
};

const found = process.argv.slice(2).flatMap(wrapsIn);

if (found.length > 0) {
  console.error("These lines continue a paragraph or a list item:\n");
  for (const line of found) {
    console.error(`  ${line}`);
  }
  console.error(`
Join each to the line before it: a paragraph or a list item is one line, as a
person types it in an editor that soft-wraps.`);
  process.exit(1);
}
