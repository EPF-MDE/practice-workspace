import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Fragment } from "react";
import { type EvidencePanel, type PanelFact, PracticeService } from "@/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { errorMessage } from "../progress";

export const evidencePanelsKey = ["evidence-panel"];

export const evidencePanelKey = (competency: string) => [
  ...evidencePanelsKey,
  competency,
];

export function useEvidencePanel(competency: string) {
  return useQuery({
    queryKey: evidencePanelKey(competency),
    queryFn: async () =>
      (await PracticeService.evidencePanelView({ path: { competency } })).data,
  });
}

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
              <li key={file.path}>
                <code>{file.path}</code>
                {typeof file.additions === "number" && ` +${file.additions}`}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

export function EvidencePanelView({
  competency,
  onMyWorkMissing,
}: {
  competency: string;
  onMyWorkMissing: () => void;
}) {
  const queryClient = useQueryClient();
  const panel = useEvidencePanel(competency);
  const refresh = useMutation({
    mutationFn: async () =>
      (await PracticeService.refreshEvidencePanel({ path: { competency } }))
        .data,
    onSuccess: (fresh) =>
      queryClient.setQueryData(evidencePanelKey(competency), fresh),
  });

  return (
    <section
      aria-label={`Your Evidence Project for ${competency}`}
      data-testid="evidence-panel"
      className="flex flex-col gap-2 rounded-lg border p-4 text-sm"
    >
      <h2 className="font-semibold">
        What the Reading Day would find on your Evidence Project
      </h2>
      {panel.isPending && <p>Reading your Evidence Project…</p>}
      {panel.isError && (
        <p role="alert">
          Your Evidence Project's panel cannot be shown just now.
        </p>
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

function PanelFindings({ panel }: { panel: EvidencePanel }) {
  return (
    <>
      {panel.empty_text && (
        <p data-testid="evidence-panel-empty" className="rounded-md border p-2">
          {panel.empty_text}
        </p>
      )}
      {panel.not_judged && panel.facts.length > 0 && (
        <p
          data-testid="evidence-panel-not-judged"
          className="text-muted-foreground"
        >
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
  panel: EvidencePanel;
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
      <div className="flex flex-col gap-2">
        <p className="text-muted-foreground">
          <code data-testid="evidence-panel-project">
            {panel.evidence_project}
          </code>
          , read{" "}
          <span data-testid="evidence-panel-read-at">
            {when(panel.read_at)}
          </span>
          ; last checked for a push{" "}
          <span data-testid="evidence-panel-checked-at">
            {when(panel.checked_at)}
          </span>
          .
        </p>
        {!panel.available && panel.unavailable && (
          <output data-testid="evidence-panel-unavailable" className="block">
            <Sentence text={panel.unavailable} />
          </output>
        )}
        <PanelFindings panel={panel} />
      </div>
      <PanelActions {...actions} />
    </>
  );
}

export function openQuestion(stepId: string) {
  const details = document.getElementById(`${stepId}-question`);
  if (!(details instanceof HTMLDetailsElement)) return;
  details.open = true;
  details.scrollIntoView({ block: "center" });
  details.querySelector("textarea")?.focus();
}
