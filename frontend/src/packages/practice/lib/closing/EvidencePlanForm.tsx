import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/packages/shared/errorMessage";
import type { Plan, useExample, useSendPlan } from "./useEvidencePlan";

export function PlanEditor({ plan, over }: { plan: Plan; over: boolean }) {
  return (
    <>
      <h3 className="text-xl font-semibold">Your Evidence Plan</h3>
      <p className="text-sm text-muted-foreground">
        {plan.isDraft
          ? "It drafts itself as you rate. Rewrite, move, remove or add lines as you like: once you edit it, your text wins."
          : "Your own text. Removing a line leaves your levels as they are."}
      </p>
      <textarea
        aria-label="Your Evidence Plan"
        rows={14}
        className={cn(
          "rounded-md border p-2 font-mono text-sm",
          plan.isDraft && "text-muted-foreground"
        )}
        value={plan.text}
        disabled={over}
        onChange={(event) => plan.edit(event.target.value)}
      />
      {!plan.isDraft && (
        <div>
          <Button
            size="sm"
            variant="outline"
            disabled={over}
            onClick={() => plan.edit(plan.draftText)}
          >
            Start again from my levels
          </Button>
        </div>
      )}
    </>
  );
}

export function ExampleField({
  example: { example, type },
  over,
}: {
  example: ReturnType<typeof useExample>;
  over: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-semibold">
        One example you will show at the Eval
      </span>
      <textarea
        name="example"
        rows={3}
        className="rounded-md border p-2"
        value={example}
        disabled={over}
        onChange={(event) => type(event.target.value)}
      />
    </label>
  );
}

function sendLabel(confirming: boolean, isDraft: boolean) {
  if (confirming) return "Confirm my Evidence Plan";
  return isDraft ? "Send the updated draft" : "Send my edited plan";
}

export function PlanSendBar({
  plan: { stored, isDraft },
  example,
  over,
  sending: { send, confirming, planChanged },
}: {
  plan: Plan;
  example: string;
  over: boolean;
  sending: ReturnType<typeof useSendPlan>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        disabled={over || send.isPending || !planChanged || !example.trim()}
        onClick={() => send.mutate()}
      >
        {sendLabel(confirming, isDraft)}
      </Button>
      {stored && (
        <span className="text-sm text-muted-foreground" data-testid="plan-sent">
          Version {stored.version} {stored.confirmed ? "confirmed" : "sent"}{" "}
          {new Date(stored.sent_at).toLocaleString()}.
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
