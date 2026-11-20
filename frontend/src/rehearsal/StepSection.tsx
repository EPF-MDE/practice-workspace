import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type CompetencyPage, RehearsalService, type StepOut } from "@/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ClosingStep } from "./closing/ClosingStep";
import { type DraftScope, drafts, errorMessage, readSteps } from "./progress";
import { QuestionField } from "./QuestionField";
import { StepBlock } from "./StepBlock";

type Props = DraftScope & {
  step: StepOut;
  page: CompetencyPage;
  closed: boolean;
  finished: boolean;
  greyed: boolean;
  licenseKey: string;
  onRead: () => void;
};

/** The step's fields as the Student types them, kept in this browser, and the request that sends them. */
function useAnswer({ studentId, competency, step }: Props) {
  const scope = { studentId, competency };
  const queryClient = useQueryClient();
  const [fields, setFields] = useState<Record<string, string>>(() => ({
    ...step.sent?.fields,
    ...drafts.get(scope, step.id),
  }));
  const send = useMutation({
    mutationFn: async () =>
      (
        await RehearsalService.sendAnswer({
          path: { competency, step_id: step.id },
          body: { fields },
        })
      ).data,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["competency", competency] }),
  });
  const update = (id: string, value: string) => {
    const next = { ...fields, [id]: value };
    setFields(next);
    drafts.set(scope, step.id, next);
  };
  const fieldIds = step.blocks.flatMap((b) =>
    b.type === "field" ? [b.id] : []
  );
  const changed =
    !step.sent ||
    fieldIds.some((id) => (fields[id] ?? "") !== (step.sent?.fields[id] ?? ""));
  return { fields, update, send, hasFields: fieldIds.length > 0, changed };
}

function StepHeading({ step }: { step: StepOut }) {
  return (
    <h2 id={`${step.id}-title`} className="text-2xl font-semibold">
      {step.title}
      {step.minutes > 0 && (
        <span className="ml-2 text-base font-normal text-muted-foreground">
          {step.minutes} min
        </span>
      )}
      {step.optional && (
        <span className="ml-2 text-base font-normal text-muted-foreground">
          optional, if you have time
        </span>
      )}
    </h2>
  );
}

function AnswerSendBar({
  step,
  closed,
  answer: { send, changed },
}: {
  step: StepOut;
  closed: boolean;
  answer: ReturnType<typeof useAnswer>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        disabled={closed || send.isPending || !changed}
        onClick={() => send.mutate()}
      >
        {step.sent ? "Send my new version" : "Send my answer"}
      </Button>
      {step.sent && (
        <span className="text-sm text-muted-foreground" data-testid="sent">
          Version {step.sent.version} sent{" "}
          {new Date(step.sent.sent_at).toLocaleString()}.
        </span>
      )}
      {!step.sent && (
        <span className="text-sm text-muted-foreground">
          What you type stays in this browser until you send it.
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

function ReadButton({ studentId, competency, step, finished, onRead }: Props) {
  return (
    <div>
      <Button
        variant="outline"
        disabled={finished}
        onClick={() => {
          readSteps.add({ studentId, competency }, step.id);
          onRead();
        }}
      >
        {finished ? "Read" : "I have read this"}
      </Button>
    </div>
  );
}

export function StepSection(props: Props) {
  const { studentId, competency, step, closed, greyed } = props;
  const answer = useAnswer(props);

  return (
    <section
      id={step.id}
      aria-labelledby={`${step.id}-title`}
      data-greyed={greyed}
      className={cn(
        "flex scroll-mt-4 flex-col gap-4 border-t pt-8",
        greyed && "opacity-50"
      )}
    >
      <StepHeading step={step} />
      {step.blocks.map((block, index) => (
        <StepBlock
          // oxlint-disable-next-line react/no-array-index-key -- a step's blocks have no id of their own and come in the content file's fixed order: the position is their identity
          key={`${step.id}-${index}`}
          studentId={studentId}
          competency={competency}
          step={step}
          block={block}
          closed={closed}
          licenseKey={props.licenseKey}
          fields={answer.fields}
          update={answer.update}
        />
      ))}
      {step.kind === "closing" && (
        <ClosingStep
          studentId={studentId}
          competency={competency}
          step={step}
          page={props.page}
        />
      )}
      {answer.hasFields && (
        <AnswerSendBar step={step} closed={closed} answer={answer} />
      )}
      {step.kind === "read" && <ReadButton {...props} />}
      <QuestionField
        studentId={studentId}
        competency={competency}
        step={step}
        closed={closed}
      />
    </section>
  );
}
