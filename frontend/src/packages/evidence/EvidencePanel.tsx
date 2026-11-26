import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { type EvidencePanel, PracticeService } from "@/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/packages/shared/errorMessage";
import { evidencePanelKey, useEvidencePanel } from "./lib/panel";
import { FactLine, NothingFoundLine, NotVisibleLine } from "./lib/PointLines";
import { Sentence } from "./lib/Sentence";

export { evidencePanelsKey } from "./lib/panel";

function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString() : "never";
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
        <ul className="flex flex-col gap-2">
          {panel.facts.map((fact) => (
            <FactLine key={`${fact.point}-${fact.text}`} fact={fact} />
          ))}
        </ul>
      )}
      {panel.nothing_found_text && (
        <p className="text-muted-foreground">{panel.nothing_found_text}</p>
      )}
      {panel.nothing_found.length > 0 && (
        <ul className="flex flex-col gap-2">
          {panel.nothing_found.map((point) => (
            <NothingFoundLine key={point.point} point={point} />
          ))}
        </ul>
      )}
      {panel.not_visible.length > 0 && (
        <ul className="flex flex-col gap-2">
          {panel.not_visible.map((point) => (
            <NotVisibleLine key={point.point} point={point} />
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
        {panel.evidence_project && (
          <p className="text-muted-foreground">
            <code data-testid="evidence-panel-project">
              {panel.evidence_project}
            </code>
            , read{" "}
            <span data-testid="evidence-panel-facts-computed-at">
              {when(panel.facts_computed_at)}
            </span>
            ; last checked for a push{" "}
            <span data-testid="evidence-panel-last-checked-at">
              {when(panel.last_checked_at)}
            </span>
            .
          </p>
        )}
        {panel.unavailable && (
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
