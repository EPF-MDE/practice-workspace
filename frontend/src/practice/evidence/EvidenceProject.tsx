import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Access, type EvidencePanel, PracticeService } from "@/client";
import { Button } from "@/components/ui/button";
import { type EvidenceDraft, errorMessage } from "../progress";
import {
  evidencePanelKey,
  evidencePanelsKey,
  Sentence,
  useEvidencePanel,
} from "./EvidencePanel";

function AccessView({ access }: { access: Access }) {
  return (
    <div data-testid="access" data-status={access.status}>
      <p className={access.status === "readable" ? "" : "font-semibold"}>
        <Sentence text={access.message} />
      </p>
      {access.how_to_make_readable && (
        <p className="text-muted-foreground">{access.how_to_make_readable}</p>
      )}
    </div>
  );
}

type Props = {
  competency: string;
  draft: EvidenceDraft;
  onDraft: (draft: EvidenceDraft | null) => void;
  ridesWithClose: boolean;
  over: boolean;
};

function useEvidenceRequests({ draft, onDraft }: Props) {
  const queryClient = useQueryClient();
  const changed = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: evidencePanelsKey }),
      queryClient.invalidateQueries({ queryKey: ["competency"] }),
    ]);
  const check = useMutation({
    mutationFn: async () =>
      (
        await PracticeService.checkProjectAccess({
          body: { url: draft.url },
        })
      ).data,
  });
  const declare = useMutation({
    mutationFn: async () =>
      (await PracticeService.declareEvidenceProject({ body: draft })).data,
    onSuccess: () => {
      onDraft(null);
      return changed();
    },
  });
  const withdraw = useMutation({
    mutationFn: async () =>
      (await PracticeService.withdrawEvidenceProject()).data,
    onSuccess: changed,
  });
  return { check, declare, withdraw };
}

type Requests = ReturnType<typeof useEvidenceRequests>;

function Declared({
  competency,
  declared,
  over,
  withdraw,
}: {
  competency: string;
  declared: NonNullable<EvidencePanel["declaration"]>;
  over: boolean;
  withdraw: Requests["withdraw"];
}) {
  const queryClient = useQueryClient();
  return (
    <div
      data-testid="declared"
      className="flex flex-col gap-2 rounded-md border p-3 text-sm"
    >
      <p>
        For every Competency, the Reading Day reads{" "}
        <a className="underline" href={declared.url}>
          {declared.url}
        </a>{" "}
        (declared {new Date(declared.declared_at).toLocaleString()}). What to
        read: {declared.what_to_read}
      </p>
      <AccessView access={declared.access} />
      <div className="flex flex-wrap gap-3">
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            queryClient.invalidateQueries({
              queryKey: evidencePanelKey(competency),
            })
          }
        >
          Check again
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={over || withdraw.isPending}
          onClick={() => withdraw.mutate()}
        >
          Withdraw it: back to the one the roster names
        </Button>
      </div>
    </div>
  );
}

function RosterEvidenceProject({ repository }: { repository?: string }) {
  return (
    <p className="text-sm" data-testid="roster-evidence-project">
      Nothing else declared: for every Competency, the Reading Day reads the
      Evidence Project the roster names
      {repository && (
        <>
          , <code>{repository}</code>
        </>
      )}
      .
    </p>
  );
}

function DeclareHelp({ panel }: { panel: EvidencePanel }) {
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="declare-help">
      <p data-testid="notice">{panel.help.notice}</p>
      <p>{panel.help.password_example}</p>
      <p>{panel.help.documentation_advice}</p>
    </div>
  );
}

type FieldProps = {
  draft: EvidenceDraft;
  over: boolean;
  edit: (next: Partial<EvidenceDraft>) => void;
};

function WhatToReadField({ draft, over, edit }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-semibold">
        A note saying what to read: a branch, a folder, a pull request, a file
      </span>
      <textarea
        name="evidence-what-to-read"
        rows={3}
        className="rounded-md border p-2"
        value={draft.what_to_read}
        disabled={over}
        onChange={(event) => edit({ what_to_read: event.target.value })}
      />
    </label>
  );
}

function DraftFields({
  draft,
  over,
  declared,
  edit,
}: FieldProps & { declared: boolean }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-semibold">
          {declared ? "Another project" : "The project"}: its address on GitHub
          or GitLab
        </span>
        <input
          name="evidence-url"
          className="rounded-md border p-2"
          placeholder="https://github.com/…"
          value={draft.url}
          disabled={over}
          onChange={(event) => edit({ url: event.target.value })}
        />
      </label>
      <WhatToReadField draft={draft} over={over} edit={edit} />
    </>
  );
}

function DraftActions({
  draft,
  over,
  ridesWithClose,
  declared,
  requests: { check, declare },
}: Pick<Props, "draft" | "over" | "ridesWithClose"> & {
  declared: boolean;
  requests: Requests;
}) {
  const filled = draft.url.trim() !== "" && draft.what_to_read.trim() !== "";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        size="sm"
        variant="outline"
        disabled={!draft.url.trim() || check.isPending}
        onClick={() => check.mutate()}
      >
        Check access
      </Button>
      {!ridesWithClose && (
        <Button
          size="sm"
          disabled={over || !filled || declare.isPending}
          onClick={() => declare.mutate()}
        >
          {declared
            ? "Change my Evidence Project"
            : "Declare this Evidence Project"}
        </Button>
      )}
      {ridesWithClose && filled && (
        <span className="text-sm text-muted-foreground">
          It is declared with your Evidence Plan when you confirm it, below.
        </span>
      )}
    </div>
  );
}

export function EvidenceProject(props: Props) {
  const { competency, draft, onDraft, over } = props;
  const panel = useEvidencePanel(competency);
  const requests = useEvidenceRequests(props);
  const { check, declare, withdraw } = requests;
  const data = panel.data;
  const declared = data?.declaration;
  const edit = (next: Partial<EvidenceDraft>) => {
    check.reset();
    onDraft({ ...draft, ...next });
  };

  return (
    <div className="flex flex-col gap-3" data-testid="evidence-project">
      <h3 className="text-xl font-semibold">Your Evidence Project</h3>
      {declared ? (
        <Declared
          competency={competency}
          declared={declared}
          over={over}
          withdraw={withdraw}
        />
      ) : (
        <RosterEvidenceProject repository={data?.evidence_project} />
      )}
      {data && <DeclareHelp panel={data} />}
      <DraftFields
        draft={draft}
        over={over}
        declared={Boolean(declared)}
        edit={edit}
      />
      <DraftActions
        {...props}
        declared={Boolean(declared)}
        requests={requests}
      />
      {check.data && <AccessView access={check.data} />}
      {(check.isError || declare.isError || withdraw.isError) && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(check.error ?? declare.error ?? withdraw.error)}
        </p>
      )}
    </div>
  );
}
