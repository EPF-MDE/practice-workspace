import type { AnswerBlock, FieldBlock, StepOut, WaitingBlock } from "@/client";
import {
  ExampleDrawingView,
  ReferenceDrawingView,
  StudentCanvas,
} from "@/packages/drawing/DrawingBlocks";
import { Html, plainText } from "@/packages/shared/Html";

type Fields = {
  fields: Record<string, string>;
  update: (id: string, value: string) => void;
};

function FieldInput({
  step,
  block,
  fields,
  update,
}: Fields & { step: StepOut; block: FieldBlock }) {
  if (block.kind === "choice")
    return (
      <div
        role="radiogroup"
        aria-label={plainText(block.label_html)}
        className="flex flex-wrap gap-x-4 gap-y-1"
      >
        {(block.options ?? []).map((option) => (
          <label key={option} className="flex items-center gap-1 text-sm">
            <input
              type="radio"
              name={`${step.id}-${block.id}`}
              value={option}
              checked={fields[block.id] === option}
              onChange={() => update(block.id, option)}
            />
            {option}
          </label>
        ))}
      </div>
    );
  const shared = {
    name: block.id,
    "aria-label": plainText(block.label_html),
    className: "rounded-md border p-2",
    value: fields[block.id] ?? "",
  };
  return block.kind === "text" ? (
    <textarea
      {...shared}
      rows={4}
      onChange={(event) => update(block.id, event.target.value)}
    />
  ) : (
    <input
      {...shared}
      onChange={(event) => update(block.id, event.target.value)}
    />
  );
}

function Answer({ block }: { block: AnswerBlock }) {
  return block.locked ? (
    <p
      data-testid="answer-locked"
      className="rounded-lg border border-dashed p-4 text-muted-foreground"
    >
      The Instructor's answer shows here once you have sent yours.
    </p>
  ) : (
    <div data-testid="answer" className="rounded-lg border bg-muted p-4">
      <h3 className="mb-2 font-semibold">The Instructor's answer</h3>
      <Html html={block.html ?? ""} />
    </div>
  );
}

function Waiting({ step, block }: { step: StepOut; block: WaitingBlock }) {
  return (
    <div
      data-testid="waiting"
      className="flex flex-col gap-2 rounded-lg border border-dashed p-4 text-muted-foreground"
    >
      <Html html={block.html} />
      <a className="text-sm underline" href={`#${block.step}`}>
        Go to {step.waits_for?.title ?? block.step}
      </a>
    </div>
  );
}

export type StepBlockProps = Fields & {
  studentId: number;
  competency: string;
  step: StepOut;
  block: StepOut["blocks"][number];
  closed: boolean;
  licenseKey: string;
};

export function StepBlock(props: StepBlockProps) {
  const { studentId, competency, step, block, closed, licenseKey } = props;
  const drawing = { studentId, competency, step, closed, licenseKey };
  switch (block.type) {
    case "point":
      return null;
    case "markdown":
      return <Html html={block.html} />;
    case "field":
      return (
        <div className="flex flex-col gap-1">
          <Html html={block.label_html} className="field-label" />
          <FieldInput
            step={step}
            block={block}
            fields={props.fields}
            update={props.update}
          />
        </div>
      );
    case "answer":
      return <Answer block={block} />;
    case "waiting":
      return <Waiting step={step} block={block} />;
    case "example-drawing":
      return <ExampleDrawingView block={block} licenseKey={licenseKey} />;
    case "canvas":
      return <StudentCanvas {...drawing} block={block} />;
    case "reference-drawing":
      return <ReferenceDrawingView {...drawing} block={block} />;
    default:
      return null;
  }
}
