import { createFileRoute } from "@tanstack/react-router";
import { courseQuery } from "@/course";
import { Path } from "@/packages/practice/Path";
import { requireStudent } from "@/session";

export const Route = createFileRoute("/competencies/$competency")({
  beforeLoad: async ({ context }) => ({
    student: await requireStudent(context.queryClient),
    course: await context.queryClient.ensureQueryData(courseQuery),
  }),
  component: CompetencyRoute,
});

function CompetencyRoute() {
  const { competency } = Route.useParams();
  const { student } = Route.useRouteContext();
  return <Path studentId={student.github_id} competency={competency} />;
}
