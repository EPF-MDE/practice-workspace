import type { CheckPointOut, CompetencyPage, PointBlock } from "@/client";
import { Button } from "@/components/ui/button";
import { Html } from "../Html";
import { errorMessage } from "../progress";
import {
  DONE,
  LEVELS,
  type Levels,
  type useSendLevels,
} from "./useSelfAssessment";

type Point = PointBlock & { type: "point" };

type PointProps = {
  point: Point;
  levels: Levels;
  closed: boolean;
  over: boolean;
};

function LevelChoices({ point, levels, closed, over }: PointProps) {
  const mine = levels.levels[point.id];
  const before = levels.sent[point.id]?.level;
  return (
    <div
      className="flex flex-wrap gap-4"
      role="radiogroup"
      aria-label={`Your level on ${point.id}`}
    >
      {LEVELS.map((level) => (
        <label key={level.id} className="flex items-center gap-1">
          <input
            type="radio"
            name={`level-${point.id}`}
            value={level.id}
            checked={mine?.level === level.id}
            disabled={
              over ||
              (closed &&
                before !== undefined &&
                level.id !== DONE &&
                level.id !== before)
            }
            onChange={() => levels.rate(point.id, { level: level.id })}
          />
          {level.label}
        </label>
      ))}
    </div>
  );
}

function DoneLink({
  point,
  link,
  over,
  rate,
}: {
  point: Point;
  link: string;
  over: boolean;
  rate: Levels["rate"];
}) {
  return (
    <div className="flex flex-col gap-1 rounded-md bg-muted p-3 text-sm">
      {point.proof_html && (
        <div>
          <span className="font-semibold">The proof: </span>
          <Html html={point.proof_html} className="inline" />
        </div>
      )}
      <label className="flex flex-col gap-1">
        The link to it, on GitHub or GitLab
        <input
          name={`link-${point.id}`}
          className="rounded-md border bg-background p-2"
          placeholder="https://github.com/…"
          value={link}
          disabled={over}
          onChange={(event) => rate(point.id, { link: event.target.value })}
        />
      </label>
    </div>
  );
}

function PointHints({
  point,
  checks,
}: {
  point: Point;
  checks: CheckPointOut[];
}) {
  return (
    <div
      className="text-sm text-muted-foreground"
      data-testid={`hints-${point.id}`}
    >
      A hint, from the check points you ticked as missed:
      <ul className="list-disc pl-5">
        {checks.map((check) => (
          <li key={check.id}>
            <Html html={check.html} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function PointFieldset(props: PointProps & { checks: CheckPointOut[] }) {
  const { point, levels, over, checks } = props;
  const mine = levels.levels[point.id];
  return (
    <fieldset
      data-testid={`point-${point.id}`}
      className="flex flex-col gap-2 rounded-lg border p-4"
    >
      <legend className="px-1 font-semibold">
        {point.id}{" "}
        <span className="font-normal text-muted-foreground">
          ({point.band})
        </span>
      </legend>
      <Html html={point.statement_html} />
      <LevelChoices {...props} />
      {mine?.level === DONE && (
        <DoneLink
          point={point}
          link={mine.link}
          over={over}
          rate={levels.rate}
        />
      )}
      {checks.length > 0 && <PointHints point={point} checks={checks} />}
    </fieldset>
  );
}

function LevelsSendBar({
  page,
  levels: { changed, missingLink },
  over,
  sendLevels,
}: {
  page: CompetencyPage;
  levels: Levels;
  over: boolean;
  sendLevels: ReturnType<typeof useSendLevels>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        disabled={
          over || sendLevels.isPending || !changed || Boolean(missingLink)
        }
        onClick={() => sendLevels.mutate()}
      >
        {page.self_assessment
          ? "Send my new Self-assessment"
          : "Send my Self-assessment"}
      </Button>
      {missingLink && (
        <span className="text-sm text-destructive">
          {missingLink[0]}: "I have done it" needs a link to your work on GitHub
          or GitLab.
        </span>
      )}
      {page.self_assessment && (
        <span className="text-sm text-muted-foreground" data-testid="sa-sent">
          Version {page.self_assessment.version} sent{" "}
          {new Date(page.self_assessment.sent_at).toLocaleString()}.
        </span>
      )}
      {sendLevels.isError && (
        <span role="alert" className="text-sm text-destructive">
          {errorMessage(sendLevels.error)}
        </span>
      )}
    </div>
  );
}

/** The Self-assessment: a level per point, with its hints, and its send. */
export function SelfAssessmentForm({
  points,
  page,
  levels,
  hints,
  sendLevels,
}: {
  points: Point[];
  page: CompetencyPage;
  levels: Levels;
  hints: Record<string, CheckPointOut[]>;
  sendLevels: ReturnType<typeof useSendLevels>;
}) {
  const over = page.reading_day_passed;
  const closed = page.closed;
  return (
    <>
      <h3 className="text-xl font-semibold">Your Self-assessment</h3>
      {closed && !over && (
        <output className="block rounded-md border p-3 text-sm">
          The workspace has closed. Until the Reading Day, a point you have not
          rated yet can still take its first level, any of the four. A point you
          have rated can only move up to "I have done it", with a link.
        </output>
      )}
      {points.map((point) => (
        <PointFieldset
          key={point.id}
          point={point}
          levels={levels}
          closed={closed}
          over={over}
          checks={hints[point.id] ?? []}
        />
      ))}
      <LevelsSendBar
        page={page}
        levels={levels}
        over={over}
        sendLevels={sendLevels}
      />
    </>
  );
}
