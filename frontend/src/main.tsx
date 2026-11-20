import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { client } from "./client/client.gen";
import "./index.css";
import { routeTree } from "./routeTree.gen";

client.setConfig({ baseURL: "", withCredentials: true });

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

const router = createRouter({ routeTree, context: { queryClient } });
declare module "@tanstack/react-router" {
  // oxlint-disable-next-line typescript/consistent-type-definitions -- augmenting the router's Register needs declaration merging, which only an interface does
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
