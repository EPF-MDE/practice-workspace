import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { SessionService } from "@/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/not-on-the-list")({
  component: NotOnTheList,
});

function NotOnTheList() {
  const refusal = useQuery({
    queryKey: ["refusal"],
    queryFn: async () => (await SessionService.refusal()).data,
  });
  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>
            <h1 className="text-2xl">You are not on the Course's list</h1>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p>
            {refusal.data?.message ??
              "You are not on the Course's list. Ask the Instructor to add you, and give them your GitHub login."}
          </p>
          <a className="underline" href="/sign-in">
            Back to the sign-in page
          </a>
        </CardContent>
      </Card>
    </main>
  );
}
