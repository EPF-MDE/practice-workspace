/**
 * "A Software Factory Circa 2022", redrawn and annotated with C1, C2 and C3.
 *
 * The original is the final slide of a third-party talk, so it is redrawn,
 * never shown as it is, and credited below it, as the course does for Jem
 * Young's slides. The annotations are the course's.
 */

const VIDEO = "https://www.youtube.com/watch?v=Ib5GBkD555M&t=220";

type Box = { x: number; y: number; lines: string[]; strong?: boolean };

const W = 130;
const H = 60;
const ROW = [40, 160, 280, 400] as const;
const COL = (i: number) => 50 + i * 155;

const BOXES: Box[] = [
  // The planning loop, then the build.
  { x: COL(0), y: ROW[0], lines: ["CEO / Vision"] },
  { x: COL(1), y: ROW[0], lines: ["Architecture", "proposal"] },
  { x: COL(2), y: ROW[0], lines: ["Sprint planning", "(1 hour on planning)"] },
  { x: COL(3), y: ROW[0], lines: ["Stuff to do"] },
  {
    x: COL(4),
    y: ROW[0],
    lines: ["Engineers:", "someone builds", "the thing"],
  },
  { x: COL(5), y: ROW[0], lines: ["Automated", "testing"] },
  // Loop #1, right to left.
  { x: COL(5), y: ROW[1], lines: ["Pull request"] },
  { x: COL(4), y: ROW[1], lines: ["CI/CD checks"] },
  { x: COL(3), y: ROW[1], lines: ["Human review"] },
  { x: COL(2), y: ROW[1], lines: ["Rollout to", "production"] },
  // Production.
  { x: COL(2), y: ROW[2], lines: ["PROD"], strong: true },
  { x: COL(3), y: ROW[2], lines: ["MONITORING"], strong: true },
  { x: COL(4), y: ROW[2], lines: ["Incidents"] },
  // Loop #2.
  { x: COL(2), y: ROW[3], lines: ["USERS"], strong: true },
  { x: COL(1), y: ROW[3], lines: ["Complaints /", "feature requests"] },
];

const mid = (i: number) => i + H / 2;
const ARROWS: string[] = [
  // Row 1, left to right.
  ...[0, 1, 2, 3, 4].map((i) => `M${COL(i) + W} ${mid(ROW[0])} H${COL(i + 1)}`),
  // Down into Loop #1, then right to left.
  `M${COL(5) + W / 2} ${ROW[0] + H} V${ROW[1]}`,
  ...[5, 4, 3].map((i) => `M${COL(i)} ${mid(ROW[1])} H${COL(i - 1) + W}`),
  // Down to PROD, then along production.
  `M${COL(2) + W / 2} ${ROW[1] + H} V${ROW[2]}`,
  `M${COL(2) + W} ${mid(ROW[2])} H${COL(3)}`,
  `M${COL(3) + W} ${mid(ROW[2])} H${COL(4)}`,
  // Incidents come back to the Engineers, between two boxes of Loop #1.
  `M${COL(4) + W} ${mid(ROW[2])} H${COL(5) - 12} V${ROW[0] + H + 20} H${COL(4) + W - 15} V${ROW[0] + H}`,
  // Loop #2: PROD to its users, their complaints, back to the vision.
  `M${COL(2) + W / 2} ${ROW[2] + H} V${ROW[3]}`,
  `M${COL(2)} ${mid(ROW[3])} H${COL(1) + W}`,
  `M${COL(1)} ${mid(ROW[3])} H${COL(0) + W / 2} V${ROW[0] + H}`,
];

const REGIONS = [
  {
    id: "C1",
    x: 35,
    y: 15,
    w: 935,
    h: 100,
    color: "#2563eb",
    note: "the planning loop, then building and testing",
  },
  {
    id: "C2",
    x: COL(2) - 15,
    y: 138,
    w: 625,
    h: 100,
    color: "#16a34a",
    note: "Loop #1: from pull request to production",
  },
  {
    id: "C3",
    x: COL(2) - 15,
    y: 258,
    w: 470,
    h: 100,
    color: "#dc2626",
    note: "production, monitoring, incidents",
  },
];

function ArrowMarker() {
  return (
    <defs>
      <marker
        id="arrow"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="7"
        markerHeight="7"
        orient="auto-start-reverse"
      >
        <path d="M0 0 L10 5 L0 10 z" fill="#525252" />
      </marker>
    </defs>
  );
}

function Region({ region }: { region: (typeof REGIONS)[number] }) {
  return (
    <g data-competency={region.id}>
      <rect
        x={region.x}
        y={region.y}
        width={region.w}
        height={region.h}
        rx={12}
        fill={region.color}
        fillOpacity={0.06}
        stroke={region.color}
        strokeDasharray="6 4"
        strokeWidth={2}
      />
      <rect
        x={region.x + 8}
        y={region.y - 11}
        width={36}
        height={22}
        rx={11}
        fill={region.color}
      />
      <text
        x={region.x + 26}
        y={region.y + 5}
        textAnchor="middle"
        fill="white"
        fontWeight={700}
        fontSize={14}
      >
        {region.id}
      </text>
    </g>
  );
}

function LoopLabels() {
  return (
    <>
      <text x={COL(5) - 14} y={ROW[1] + H + 30} fontSize={12} fill="#16a34a">
        Loop #1
      </text>
      <text
        x={COL(0) + W / 2 - 8}
        y={ROW[2] + 10}
        fontSize={12}
        fill="#525252"
        transform={`rotate(-90 ${COL(0) + W / 2 - 8} ${ROW[2] + 10})`}
      >
        Loop #2
      </text>
    </>
  );
}

function Arrow({ d }: { d: string }) {
  return (
    <path
      d={d}
      fill="none"
      stroke="#525252"
      strokeWidth={1.5}
      markerEnd="url(#arrow)"
    />
  );
}

function BoxView({ box }: { box: Box }) {
  return (
    <g>
      <rect
        x={box.x}
        y={box.y}
        width={W}
        height={H}
        rx={8}
        fill="white"
        stroke="#262626"
        strokeWidth={box.strong ? 2 : 1}
      />
      <text
        x={box.x + W / 2}
        y={box.y + H / 2 - ((box.lines.length - 1) * 15) / 2 + 5}
        textAnchor="middle"
        fontSize={13}
        fontWeight={box.strong ? 700 : 400}
        fill="#171717"
      >
        {box.lines.map((line, index) => (
          <tspan key={line} x={box.x + W / 2} dy={index === 0 ? 0 : 15}>
            {line}
          </tspan>
        ))}
      </text>
    </g>
  );
}

function Diagram() {
  return (
    <svg
      viewBox="0 0 1000 480"
      role="img"
      aria-label="A Software Factory Circa 2022, annotated with C1, C2 and C3"
      className="w-full rounded-lg border bg-white"
      fontFamily="ui-sans-serif, system-ui, sans-serif"
    >
      <ArrowMarker />
      {REGIONS.map((region) => (
        <Region key={region.id} region={region} />
      ))}
      <LoopLabels />
      {ARROWS.map((d) => (
        <Arrow key={d} d={d} />
      ))}
      {BOXES.map((box) => (
        <BoxView key={box.lines.join(" ")} box={box} />
      ))}
    </svg>
  );
}

function Credit() {
  return (
    <figcaption id="factory-caption" className="text-sm text-muted-foreground">
      Redrawn from "A Software Factory Circa 2022", the final slide of Dex
      Horthy's talk{" "}
      <a className="underline" href={VIDEO} target="_blank" rel="noreferrer">
        <cite>Why Software Factories Fail</cite>
      </a>{" "}
      (AI Engineer World's Fair 2026). Watch 3:40 to 5:45, in the chapter "A
      brief history of the software factory".
    </figcaption>
  );
}

export function SoftwareFactory() {
  return (
    <figure className="flex flex-col gap-3" aria-labelledby="factory-caption">
      <Diagram />
      <ul className="grid gap-1 text-sm md:grid-cols-3">
        {REGIONS.map((region) => (
          <li key={region.id}>
            <span className="font-semibold" style={{ color: region.color }}>
              {region.id}
            </span>{" "}
            {region.note}
          </li>
        ))}
      </ul>
      <Credit />
    </figure>
  );
}
