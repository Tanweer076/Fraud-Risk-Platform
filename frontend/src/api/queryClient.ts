import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Client errors (bad filter, not found, no access) won't fix themselves on retry.
        retry: (failures, error) =>
          !(error instanceof ApiError && error.status < 500) && failures < 2,
      },
    },
  });
}
