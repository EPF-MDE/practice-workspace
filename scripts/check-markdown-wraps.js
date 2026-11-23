import { readFileSync } from "node:fs";

const FENCE = /^(`{3,}|~{3,})/;
const HEADING = /^#{1,6}(\s|$)/;
const TABLE_ROW = /^\|/;
const TABLE_DELIMITER = /^\|?\s*:?-+:?\s*(\|\s*:?-*:?\s*)+\|?$/;
const HTML = /^</;
const DIRECTIVE = /^:::/;
const RULE = /^([-*_=])(\s*\1){2,}\s*$/;
const LIST_ITEM = /^([-*+]|\d+[.)])\s/;
const QUOTE = /^>/;
const LINK_DEFINITION = /^\[[^\]]+\]:\s/;
const INDENTED_CODE = /^( {4}|\t)/;
const HARD_BREAK = /( {2}|\\)$/;

const HOLDS_NO_PROSE = [HEADING, TABLE_ROW, HTML, DIRECTIVE, RULE];
const STARTS_A_BLOCK = [...HOLDS_NO_PROSE, LIST_ITEM, QUOTE, LINK_DEFINITION];

const matchesAny = (patterns, text) =>
  patterns.some((pattern) => pattern.test(text));

const BLANK = { prose: false, quoted: false, table: false, code: false };

const skippedBlock = (text, index) => {
  if (index === 0 && text === "---") {
    return (line) => line === "---";
  }
  const fence = text.match(FENCE);
  if (fence) {
    const closing = new RegExp(`^${fence[1][0]}{${fence[1].length},}\\s*$`);
    return (line) => closing.test(line);
  }
  if (text.startsWith("<!--") && !text.includes("-->")) {
    return (line) => line.includes("-->");
  }
  return null;
};

const startsATable = (content, next, previous) =>
  (previous.table && content.includes("|")) ||
  (content.includes("|") && TABLE_DELIMITER.test(next ?? ""));

const lineAfter = (line, previous, next) => {
  const text = line.trim();
  const quoted = QUOTE.test(text);
  const content = text.replace(/^(>\s?)+/, "");
  if (content === "") return { state: BLANK, wraps: false };
  const code = INDENTED_CODE.test(line) && (previous.code || !previous.prose);
  const table = !code && startsATable(content, next, previous);
  const wraps =
    !code &&
    !table &&
    previous.prose &&
    !previous.hardBreak &&
    previous.quoted === quoted &&
    !matchesAny(STARTS_A_BLOCK, quoted ? content : text);
  const prose = !code && !table && !matchesAny(HOLDS_NO_PROSE, content);
  const hardBreak = HARD_BREAK.test(line);
  return { state: { prose, quoted, table, code, hardBreak }, wraps };
};

const wrapsIn = (file) => {
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  const found = [];
  let closes = null;
  let previous = BLANK;

  lines.forEach((line, index) => {
    const text = line.trim();
    if (closes !== null) {
      if (closes(text)) closes = null;
      return;
    }
    closes = skippedBlock(text, index);
    if (closes !== null || text.startsWith("<!--")) {
      previous = BLANK;
      return;
    }
    const next = lines[index + 1]?.trim().replace(/^(>\s?)+/, "");
    const after = lineAfter(line, previous, next);
    if (after.wraps) found.push(`${file}:${index + 1}: ${text.slice(0, 60)}`);
    previous = after.state;
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
