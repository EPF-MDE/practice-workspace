import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type Access, type EvidencePanel, RehearsalService } from "@/client";
import { Button } from "@/components/ui/button";
import { type EvidenceDraft, errorMessage } from "../progress";
import { evidencePanelKey, Sentence, useEvidencePanel } from "./EvidencePanel";

function AccessView({ access }: { access: Access }) {
  return (
    <div data-testid="access" data-status={access.status}>
      <p className={access.status === "readable" ? "" : "font-semibold"}>
        <Sentence text={access.message} />
      </p>
      {access.how && <p className="text-muted-foreground">{access.how}</p>}
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

/** The requests of the Evidence Project: check its access, declare it, withdraw it. */
function useEvidenceRequests({ competency, draft, onDraft }: Props) {
  const queryClient = useQueryClient();
  const shown = (fresh: EvidencePanel | undefined) => {
    queryClient.setQueryData(evidencePanelKey(competency), fresh);
    return queryClient.invalidateQueries({
      queryKey: ["competency", competency],
    });
  };
  const check = useMutation({
    mutationFn: async () =>
      (
        await RehearsalService.checkProjectAccess({
          path: { competency },
          body: { url: draft.url },
        })
      ).data,
  });
  const declare = useMutation({
    mutationFn: async () =>
      (
        await RehearsalService.declareEvidenceProject({
          path: { competency },
          body: draft,
        })
      ).data,
    onSuccess: (fresh) => {
      onDraft(null);
      return shown(fresh);
    },
  });
  const withdraw = useMutation({
    mutationFn: async () =>
      (await RehearsalService.withdrawEvidenceProject({ path: { competency } }))
        .data,
    onSuccess: shown,
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
        For {competency}, the Reading Day reads{" "}
        <a className="underline" href={declared.url}>
          {declared.url}
        </a>{" "}
        (declared {new Date(declared.declared_at).toLocaleString()}). What to
        read: {declared.note}
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
          Withdraw it: read my repository
        </Button>
      </div>
    </div>
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

function NoteField({ draft, over, edit }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-semibold">
        A note saying what to read: a branch, a folder, a pull request, a file
      </span>
      <textarea
        name="evidence-note"
        rows={3}
        className="rounded-md border p-2"
        value={draft.note}
        disabled={over}
        onChange={(event) => edit({ note: event.target.value })}
      />
    </label>
  );
}

function DraftFields({
  draft,
  over,
  declared,
  repository,
  edit,
}: FieldProps & { declared: boolean; repository: string | undefined }) {
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
      {repository !== undefined && (
        <div>
          <button
            type="button"
            className="text-sm underline"
            disabled={over}
            onClick={() => edit({ url: `https://github.com/${repository}` })}
          >
            Declare my repository instead
          </button>
        </div>
      )}
      <NoteField draft={draft} over={over} edit={edit} />
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
  const filled = draft.url.trim() !== "" && draft.note.trim() !== "";
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

/**
 * The Evidence Project of one Competency, in its closing step. Declared there
 * before the Evidence Plan is confirmed, it rides with that one send; after,
 * a change or a withdrawal is its own send, until the Reading Day.
 */
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
        <p className="text-sm">
          None declared: the Reading Day reads your repository for {competency}.
        </p>
      )}
      {data && <DeclareHelp panel={data} />}
      <DraftFields
        draft={draft}
        over={over}
        declared={Boolean(declared)}
        repository={data?.repository}
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
