import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PracticeService, type StepOut } from "@/client";
import { Button } from "@/components/ui/button";
import { type DraftScope, drafts, errorMessage } from "./progress";
import { pathKey } from "./pathKeys";

type Props = DraftScope & { step: StepOut; closed: boolean };

function useQuestion({ studentId, competency, step }: Props) {
  const scope = { studentId, competency };
  const queryClient = useQueryClient();
  const [text, setText] = useState(() => drafts.getQuestion(scope, step.id));
  const type = (next: string) => {
    setText(next);
    drafts.setQuestion(scope, step.id, next);
  };
  const ask = useMutation({
    mutationFn: async () =>
      (
        await PracticeService.askQuestion({
          path: { competency, step_id: step.id },
          body: { text },
        })
      ).data,
    onSuccess: () => {
      type("");
      return queryClient.invalidateQueries({
        queryKey: pathKey(competency),
      });
    },
  });
  return { text, type, ask };
}

export function QuestionField(props: Props) {
  const { step, closed } = props;
  const { text, type, ask } = useQuestion(props);
  return (
    <details
      id={`${step.id}-question`}
      className="rounded-lg border p-3 text-sm"
    >
      <summary className="cursor-pointer">
        Ask the Instructor a question
      </summary>
      <div className="mt-3 flex flex-col gap-2">
        {step.questions.length > 0 && (
          <ul className="list-disc pl-5" aria-label="Your questions">
            {step.questions.map((q) => (
              <li key={q.asked_at}>{q.text}</li>
            ))}
          </ul>
        )}
        <textarea
          aria-label={`Your question on ${step.title}`}
          rows={3}
          className="rounded-md border p-2"
          value={text}
          onChange={(event) => type(event.target.value)}
        />
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            disabled={closed || ask.isPending || !text.trim()}
            onClick={() => ask.mutate()}
          >
            Send my question
          </Button>
          {ask.isError && (
            <span role="alert" className="text-destructive">
              {errorMessage(ask.error)}
            </span>
          )}
        </div>
      </div>
    </details>
  );
}
