import { Fragment } from "react";

function sentenceParts(text: string) {
  const parts = text.split("`");
  return parts.map((part, index) => ({
    part,
    code: index % 2 === 1,
    at: parts
      .slice(0, index)
      .reduce((sum, before) => sum + before.length + 1, 0),
  }));
}

export function Sentence({ text }: { text: string }) {
  return (
    <>
      {sentenceParts(text).map(({ part, code, at }) =>
        code ? (
          <code key={at} className="rounded bg-muted px-1 text-[0.9em]">
            {part}
          </code>
        ) : (
          <Fragment key={at}>{part}</Fragment>
        )
      )}
    </>
  );
}
