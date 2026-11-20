import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { SessionService } from "@/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/sign-in")({
  component: SignIn,
});

function SignIn() {
  const page = useQuery({
    queryKey: ["sign-in"],
    queryFn: async () => (await SessionService.signInPage()).data,
  });
  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>
            <h1 className="text-2xl">Practice workspace</h1>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <p className="text-muted-foreground">{page.data?.notice}</p>
          <Button asChild size="lg">
            <a href={page.data?.sign_in_url ?? "/auth/login"}>
              Sign in with GitHub
            </a>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
