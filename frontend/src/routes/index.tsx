import { createFileRoute, Link } from "@tanstack/react-router";
import { SoftwareFactory } from "@/components/SoftwareFactory";
import { Button } from "@/components/ui/button";
import { requireStudent } from "@/session";

export const Route = createFileRoute("/")({
  beforeLoad: async ({ context }) => ({
    student: await requireStudent(context.queryClient),
  }),
  component: Opening,
});

const COMPETENCIES = [
  {
    id: "C1",
    statement:
      "Design a resilient web architecture under non-functional constraints",
  },
  { id: "C2", statement: "Industrialize a service through a CI/CD pipeline" },
  {
    id: "C3",
    statement: "Observe, prioritize, and resolve errors in production",
  },
];

function Opening() {
  const { student } = Route.useRouteContext();
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 p-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Practice workspace</h1>
          <p className="text-muted-foreground">
            {student.name}, your Project is{" "}
            <strong data-testid="project">{student.project}</strong>.
          </p>
        </div>
        <form method="post" action="/auth/logout">
          <Button variant="outline" size="sm" type="submit">
            Sign out
          </Button>
        </form>
      </header>

      <SoftwareFactory />

      <section aria-labelledby="path" className="flex flex-col gap-3">
        <h2 id="path" className="text-xl font-semibold">
          Your path: three Competencies, 40 minutes each
        </h2>
        <ol className="grid gap-3 md:grid-cols-3">
          {COMPETENCIES.map((competency) => (
            <li key={competency.id} className="rounded-lg border p-4">
              <Link
                to="/competencies/$competency"
                params={{ competency: competency.id }}
                className="hover:underline"
              >
                <span className="font-semibold">{competency.id}</span>{" "}
                {competency.statement}
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
