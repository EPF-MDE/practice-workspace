import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, type ReactNode, Suspense, useState } from "react";
import type { Editor } from "tldraw";
import {
  type CanvasBlock,
  type DrawingIn,
  type ExampleDrawingBlock,
  type ReferenceDrawingBlock,
  PracticeService,
  type StepOut,
} from "@/client";
import { Button } from "@/components/ui/button";
import { Html } from "@/packages/shared/Html";
import { closingDrafts, drafts } from "@/packages/shared/drafts";
import { errorMessage } from "@/packages/shared/errorMessage";
import type { Snapshot } from "./lib/views";
import { pathKey } from "@/packages/shared/pathKeys";

const views = () => import("./lib/views");
const ReadOnlyDrawing = lazy(() =>
  views().then((m) => ({ default: m.ReadOnlyDrawing }))
);
const EditableDrawing = lazy(() =>
  views().then((m) => ({ default: m.EditableDrawing }))
);

function Frame({
  label,
  tall,
  children,
}: {
  label: string;
  tall?: boolean;
  children: ReactNode;
}) {
  return (
    <figure
      aria-label={label}
      className={`relative w-full overflow-clip rounded-lg border ${tall ? "h-[32rem]" : "h-80"}`}
    >
      <Suspense
        fallback={<p className="p-4 text-muted-foreground">Loading…</p>}
      >
        {children}
      </Suspense>
    </figure>
  );
}

export function ExampleDrawingView({
  block,
  licenseKey,
}: {
  block: ExampleDrawingBlock;
  licenseKey: string;
}) {
  return (
    <div className="flex flex-col gap-2" data-testid="example-drawing">
      <h3 className="font-semibold">An Example Drawing</h3>
      <Frame label="Example Drawing">
        <ReadOnlyDrawing
          snapshot={block.snapshot as Snapshot}
          licenseKey={licenseKey}
        />
      </Frame>
      <Html html={block.caption_html} className="text-sm" />
    </div>
  );
}

type CanvasProps = {
  studentId: number;
  competency: string;
  step: StepOut;
  block: CanvasBlock;
  closed: boolean;
  licenseKey: string;
};

export function StudentCanvas(props: CanvasProps) {
  const { studentId, competency, step } = props;
  const [draft] = useState(() =>
    drafts.getDrawing({ studentId, competency }, step.id)
  );
  const sent = useQuery({
    queryKey: ["drawing", competency, step.id],
    queryFn: async () =>
      (
        await PracticeService.myDrawing({
          path: { competency, step_id: step.id },
        })
      ).data,
    enabled: !draft && Boolean(step.drawing),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const initial = draft ?? sent.data?.snapshot ?? null;
  const ready = draft || !step.drawing || !sent.isPending;
  return (
    <div className="flex flex-col gap-2" data-testid="my-drawing">
      <Html html={props.block.prompt_html} />
      {ready ? (
        <CanvasAndSend {...props} initial={initial as Snapshot | null} />
      ) : (
        <Frame label="Your drawing" tall>
          <p className="p-4 text-muted-foreground">Loading your drawing…</p>
        </Frame>
      )}
    </div>
  );
}

function useSendDrawing(
  competency: string,
  step: StepOut,
  editor: Editor | null
) {
  const queryClient = useQueryClient();
  const [empty, setEmpty] = useState(false);
  const send = useMutation({
    mutationFn: async () => {
      const { exportDrawing } = await views();
      const drawing = editor && (await exportDrawing(editor));
      if (!drawing) {
        setEmpty(true);
        return null;
      }
      setEmpty(false);
      return (
        await PracticeService.sendDrawing({
          path: { competency, step_id: step.id },
          body: {
            png_base64: drawing.png_base64,
            snapshot: { ...drawing.snapshot },
          } satisfies DrawingIn,
        })
      ).data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: pathKey(competency) }),
  });
  return { send, empty };
}

function DrawingSendBar({
  step,
  disabled,
  kept,
  sending: { send, empty },
}: {
  step: StepOut;
  disabled: boolean;
  kept: boolean;
  sending: ReturnType<typeof useSendDrawing>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        disabled={disabled || send.isPending}
        onClick={() => send.mutate()}
      >
        {step.drawing ? "Send my new version" : "Send my drawing"}
      </Button>
      {step.drawing ? (
        <span
          className="text-sm text-muted-foreground"
          data-testid="drawing-sent"
        >
          Version {step.drawing.version} sent{" "}
          {new Date(step.drawing.sent_at).toLocaleString()}.
        </span>
      ) : (
        <span className="text-sm text-muted-foreground">
          Your drawing stays in this browser until you send it.
        </span>
      )}
      {empty && (
        <span role="alert" className="text-sm text-destructive">
          Draw something before sending.
        </span>
      )}
      {!kept && (
        <span role="alert" className="text-sm text-destructive">
          This browser is out of room to keep your drawing: send it now.
        </span>
      )}
      {send.isError && (
        <span role="alert" className="text-sm text-destructive">
          {errorMessage(send.error)}
        </span>
      )}
    </div>
  );
}

function CanvasAndSend({
  studentId,
  competency,
  step,
  closed,
  licenseKey,
  initial,
}: CanvasProps & { initial: Snapshot | null }) {
  const [editor, setEditor] = useState<Editor | null>(null);
  const [kept, setKept] = useState(true);
  const sending = useSendDrawing(competency, step, editor);
  return (
    <>
      <Frame label="Your drawing" tall>
        <EditableDrawing
          initial={initial}
          licenseKey={licenseKey}
          readOnly={closed}
          onEditor={setEditor}
          onChange={(snapshot) =>
            setKept(
              drafts.setDrawing({ studentId, competency }, step.id, snapshot)
            )
          }
        />
      </Frame>
      <DrawingSendBar
        step={step}
        disabled={closed || !editor}
        kept={kept}
        sending={sending}
      />
    </>
  );
}

export function ReferenceDrawingView({
  studentId,
  competency,
  step,
  block,
  closed,
  licenseKey,
}: {
  studentId: number;
  competency: string;
  step: StepOut;
  block: ReferenceDrawingBlock;
  closed: boolean;
  licenseKey: string;
}) {
  if (block.locked || !block.snapshot)
    return (
      <p
        data-testid="reference-locked"
        className="rounded-lg border border-dashed p-4 text-muted-foreground"
      >
        The Instructor's drawing and its check points show here once you have
        sent yours.
      </p>
    );
  return (
    <div
      className="flex flex-col gap-3 rounded-lg border bg-muted p-4"
      data-testid="reference-drawing"
    >
      <h3 className="font-semibold">The Instructor's drawing</h3>
      <Frame label="Reference Drawing">
        <ReadOnlyDrawing
          snapshot={block.snapshot as Snapshot}
          licenseKey={licenseKey}
        />
      </Frame>
      <Html html={block.caption_html ?? ""} className="text-sm" />
      <CheckPoints
        studentId={studentId}
        competency={competency}
        step={step}
        block={block}
        closed={closed}
      />
    </div>
  );
}

function CheckPoints({
  studentId,
  competency,
  step,
  block,
  closed,
}: {
  studentId: number;
  competency: string;
  step: StepOut;
  block: ReferenceDrawingBlock;
  closed: boolean;
}) {
  const [missed, setMissed] = useState<string[]>(
    () =>
      closingDrafts.getTicks({ studentId, competency }, step.id) ??
      step.missed_check_points ??
      []
  );
  const tick = (id: string, checked: boolean) => {
    const next = checked ? [...missed, id] : missed.filter((m) => m !== id);
    setMissed(next);
    closingDrafts.setTicks({ studentId, competency }, step.id, next);
  };
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="font-semibold">
        Tick the check points your drawing missed
      </legend>
      <p className="text-sm text-muted-foreground">
        Your ticks stay in this browser. They are sent with your
        Self-assessment, at the end of {competency}, and show beside the
        matching point as a hint.
      </p>
      {(block.check_points ?? []).map((check) => (
        <label key={check.id} className="flex items-start gap-2">
          <input
            type="checkbox"
            name={check.id}
            className="mt-1"
            checked={missed.includes(check.id)}
            disabled={closed}
            onChange={(event) => tick(check.id, event.target.checked)}
          />
          <Html html={check.html} />
        </label>
      ))}
    </fieldset>
  );
}
