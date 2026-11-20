import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    component: () => (
      <div className="min-h-screen">
        <Outlet />
      </div>
    ),
    notFoundComponent: () => (
      <main className="mx-auto max-w-xl p-8">
        <h1 className="text-xl font-semibold">This page does not exist</h1>
        <a className="underline" href="/">
          Back to the workspace
        </a>
      </main>
    ),
  }
);
