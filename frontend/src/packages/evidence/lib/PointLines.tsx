import type { ReactNode } from "react";
import type { NothingFound, NotVisible, PanelFact } from "@/client";
import { Sentence } from "./Sentence";

function PointLine({
  testId,
  point,
  statement,
  children,
}: {
  testId: string;
  point: string;
  statement: string | null;
  children: ReactNode;
}) {
  return (
    <li data-testid={testId} className="flex flex-col gap-1">
      <span>
        <span className="font-semibold">{point}</span>
        {statement && <>: {statement}</>}
      </span>
      {children}
    </li>
  );
}

function ChangedFiles({ fact }: { fact: PanelFact }) {
  const files = fact.files ?? [];
  if (files.length === 0) return null;
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer">The {files.length} files</summary>
      <ul className="pl-4">
        {files.map((file) => (
          <li key={file.path}>
            <code>{file.path}</code>
            {typeof file.additions === "number" && ` +${file.additions}`}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function FactLine({ fact }: { fact: PanelFact }) {
  const credited =
    fact.credited_to !== "student"
      ? ` (the code of \`${fact.credited_to}\`, credited to it)`
      : "";
  return (
    <PointLine
      testId={`fact-${fact.point}`}
      point={fact.point}
      statement={fact.statement}
    >
      <span className="text-muted-foreground">
        Found: <Sentence text={fact.text + credited} />
        {fact.link && (
          <>
            {" "}
            <a
              className="underline"
              href={fact.link}
              target="_blank"
              rel="noreferrer"
            >
              see it
            </a>
          </>
        )}
      </span>
      <ChangedFiles fact={fact} />
    </PointLine>
  );
}

export function NothingFoundLine({ point }: { point: NothingFound }) {
  return (
    <PointLine
      testId={`nothing-found-${point.point}`}
      point={point.point}
      statement={point.statement}
    >
      <span className="text-muted-foreground">
        Nothing found yet.
        {point.to_get_there && <> To get there: {point.to_get_there}</>}
      </span>
    </PointLine>
  );
}

export function NotVisibleLine({ point }: { point: NotVisible }) {
  return (
    <PointLine
      testId={`not-visible-${point.point}`}
      point={point.point}
      statement={point.statement}
    >
      <span className="text-muted-foreground">{point.text}</span>
    </PointLine>
  );
}
