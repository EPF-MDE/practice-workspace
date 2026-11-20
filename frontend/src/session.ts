import type { QueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";
import { AxiosError } from "axios";
import { type Me, SessionService } from "@/client";

export const meQuery = {
  queryKey: ["me"],
  queryFn: async (): Promise<Me | null> => {
    try {
      return (await SessionService.me()).data;
    } catch (error) {
      if (error instanceof AxiosError && error.response?.status === 401) {
        return null;
      }
      throw error;
    }
  },
  staleTime: 60_000,
};

export async function requireStudent(queryClient: QueryClient): Promise<Me> {
  const me = await queryClient.fetchQuery(meQuery);
  if (!me) {
    throw redirect({ to: "/sign-in" });
  }
  return me;
}
