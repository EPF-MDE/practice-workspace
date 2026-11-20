import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Fragment } from "react";
import { type ForkPanel, type PanelFact, RehearsalService } from "@/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { errorMessage } from "../progress";

export const forkKey = (competency: string) => ["fork", competency];

/** The fork panel of one Competency: read from the server, shared by the sidebar and the closing step. */
export function useForkPanel(competency: string) {
  return useQuery({
    queryKey: forkKey(competency),
    queryFn: async () =>
      (await RehearsalService.forkPanelView({ path: { competency } })).data,
  });
}

/** The parts of a sentence, split on backticks, each keyed by where it starts. */
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

/** A sentence whose `code` spans (branch names, files) are shown as code. */
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

function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString() : "never";
}

function Fact({ fact }: { fact: PanelFact }) {
  const credited =
    fact.credited_to !== "student"
      ? ` (the code of \`${fact.credited_to}\`, credited to it)`
      : "";
  return (
    <li data-testid={`fact-${fact.point}`} className="flex flex-col gap-1">
      <span>
        <Sentence text={fact.text + credited} />{" "}
        <span className="whitespace-nowrap font-semibold">→ {fact.point}</span>
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
      {(fact.files ?? []).length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            The {fact.files?.length} files
          </summary>
          <ul className="pl-4">
            {fact.files?.map((file) => (
              <li key={String(file.path)}>
                <code>{String(file.path)}</code> +{String(file.additions)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

/**
 * What the Reading Day would find on the Student's fork today, for one
 * Competency: facts naming the point they support, never a Band.
 */
export function ForkPanelView({
  competency,
  onMyWorkMissing,
  title = "What the Reading Day would find on your fork",
}: {
  competency: string;
  onMyWorkMissing: () => void;
  title?: string;
}) {
  const queryClient = useQueryClient();
  const panel = useForkPanel(competency);
  const refresh = useMutation({
    mutationFn: async () =>
      (await RehearsalService.refreshForkPanel({ path: { competency } })).data,
    onSuccess: (fresh) => queryClient.setQueryData(forkKey(competency), fresh),
  });

  return (
    <section
      aria-label={`Your fork for ${competency}`}
      data-testid="fork-panel"
      className="flex flex-col gap-2 rounded-lg border p-4 text-sm"
    >
      <h2 className="font-semibold">{title}</h2>
      {panel.isPending && <p>Reading your fork…</p>}
      {panel.isError && (
        <p role="alert">Your fork's panel cannot be shown just now.</p>
      )}
      {panel.data && (
        <PanelBody
          panel={panel.data}
          onMyWorkMissing={onMyWorkMissing}
          refreshing={refresh.isPending}
          onRefresh={() => refresh.mutate()}
        />
      )}
      {refresh.isError && (
        <p role="alert" className="text-destructive">
          {errorMessage(refresh.error)}
        </p>
      )}
    </section>
  );
}

function PanelFindings({ panel }: { panel: ForkPanel }) {
  return (
    <>
      {panel.empty_text && (
        <p data-testid="fork-empty" className="rounded-md border p-2">
          {panel.empty_text}
        </p>
      )}
      {panel.not_judged && panel.facts.length > 0 && (
        <p data-testid="fork-not-judged" className="text-muted-foreground">
          {panel.not_judged}
        </p>
      )}
      {panel.facts.length > 0 && (
        <ul className="flex list-disc flex-col gap-2 pl-5">
          {panel.facts.map((fact) => (
            <Fact key={`${fact.point}-${fact.text}`} fact={fact} />
          ))}
        </ul>
      )}
      {panel.nothing_found_text && (
        <p className="text-muted-foreground">{panel.nothing_found_text}</p>
      )}
      {panel.not_visible.length > 0 && (
        <ul className="flex flex-col gap-1">
          {panel.not_visible.map((n) => (
            <li key={n.point} data-testid={`not-visible-${n.point}`}>
              <span className="font-semibold">{n.point}</span>: {n.text}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

type PanelBodyProps = {
  panel: ForkPanel;
  onMyWorkMissing: () => void;
  refreshing: boolean;
  onRefresh: () => void;
};

function PanelActions({
  onMyWorkMissing,
  refreshing,
  onRefresh,
}: Omit<PanelBodyProps, "panel">) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        size="sm"
        variant="outline"
        disabled={refreshing}
        onClick={onRefresh}
      >
        <RefreshCw className={cn("size-4", refreshing && "animate-spin")} />
        Refresh
      </Button>
      <button type="button" className="underline" onClick={onMyWorkMissing}>
        My work doesn't show here
      </button>
    </div>
  );
}

function PanelBody({ panel, ...actions }: PanelBodyProps) {
  return (
    <>
      {panel.greyed && panel.greyed_text && (
        <p data-testid="fork-greyed" className="rounded-md bg-muted p-2">
          <Sentence text={panel.greyed_text} />.
        </p>
      )}
      <div
        className={cn("flex flex-col gap-2", panel.greyed && "opacity-50")}
        data-greyed={panel.greyed}
      >
        <p className="text-muted-foreground">
          <code>{panel.fork}</code>, read{" "}
          <span data-testid="fork-read-at">{when(panel.read_at)}</span>; last
          checked for a push{" "}
          <span data-testid="fork-checked-at">{when(panel.checked_at)}</span>.
        </p>
        {!panel.available && (
          <output className="block">{panel.unavailable}</output>
        )}
        <PanelFindings panel={panel} />
      </div>
      <PanelActions {...actions} />
    </>
  );
}

/** Opens a step's question field, so the Student can say where their work is. */
export function openQuestion(stepId: string) {
  const details = document.getElementById(`${stepId}-question`);
  if (!(details instanceof HTMLDetailsElement)) return;
  details.open = true;
  details.scrollIntoView({ block: "center" });
  details.querySelector("textarea")?.focus();
}
