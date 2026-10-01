/** React Query hooks, one per API call. Pages never call fetch directly. */
import {
  keepPreviousData,
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  api,
  apiFetch,
  type Band,
  type Batch,
  type BulkApproveResult,
  type Page,
  type PredictionRequest,
  type Review,
  type Role,
  type ScoreResult,
  unwrap,
} from "./client";

export interface TransactionFilters {
  period?: string;
  band?: Band[];
  min_score?: number;
  max_score?: number;
  break_type?: string;
  suspicious?: boolean;
  currency?: string;
  country?: string;
  account?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  reviewed?: boolean;
}

/** Scoring or reviewing changes the lists, the queue and the dashboard numbers. */
function invalidateActivity(client: QueryClient) {
  for (const key of ["transactions", "transaction", "analytics", "reviews"]) {
    void client.invalidateQueries({ queryKey: [key] });
  }
}

// Analytics ---------------------------------------------------------------------------------

export function useSummary(period?: string) {
  return useQuery({
    queryKey: ["analytics", "summary", period ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/analytics/summary", { params: { query: { period } } })),
    placeholderData: keepPreviousData,
  });
}

export function useRiskDistribution(period?: string) {
  return useQuery({
    queryKey: ["analytics", "risk-distribution", period ?? null],
    queryFn: () =>
      unwrap(api.GET("/api/v1/analytics/risk-distribution", { params: { query: { period } } })),
    placeholderData: keepPreviousData,
  });
}

export function useTrends(granularity: "day" | "month", period?: string) {
  return useQuery({
    queryKey: ["analytics", "trends", granularity, period ?? null],
    queryFn: () =>
      unwrap(api.GET("/api/v1/analytics/trends", { params: { query: { granularity, period } } })),
    placeholderData: keepPreviousData,
  });
}

export type BreakdownBy = "currency" | "country" | "description" | "period" | "band" | "break_type";

export function useBreakdown(by: BreakdownBy, period?: string, limit = 50) {
  return useQuery({
    queryKey: ["analytics", "breakdown", by, period ?? null, limit],
    queryFn: () =>
      unwrap(api.GET("/api/v1/analytics/breakdown", { params: { query: { by, period, limit } } })),
    placeholderData: keepPreviousData,
  });
}

export function useTopAccounts(period?: string, limit = 10) {
  return useQuery({
    queryKey: ["analytics", "top-accounts", period ?? null, limit],
    queryFn: () =>
      unwrap(api.GET("/api/v1/analytics/top-accounts", { params: { query: { period, limit } } })),
    placeholderData: keepPreviousData,
  });
}

// Transactions and scoring ------------------------------------------------------------------

export function useTransactions(
  filters: TransactionFilters,
  sort: string,
  page: number,
  pageSize = 50,
) {
  return useQuery({
    queryKey: ["transactions", filters, sort, page, pageSize],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/transactions", {
          params: { query: { ...filters, sort, page, page_size: pageSize } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useTransaction(transactionId: string) {
  return useQuery({
    queryKey: ["transaction", transactionId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/transactions/{transaction_id}", {
          params: { path: { transaction_id: transactionId } },
        }),
      ),
  });
}

export function useScoreTransaction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PredictionRequest): Promise<ScoreResult> =>
      unwrap(api.POST("/api/v1/predictions", { body })),
    onSuccess: () => invalidateActivity(client),
  });
}

/** Query string for the export: the same filters as the list, with bands repeated. */
export function filtersQuery(filters: TransactionFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
    else params.set(key, String(value));
  }
  return params;
}

/** Download the filtered transactions as CSV (the API needs the token, so a plain link won't do). */
export async function downloadTransactionsCsv(filters: TransactionFilters) {
  const response = await apiFetch(`/api/v1/reports/export?${filtersQuery(filters)}`);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "transactions.csv";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Reviews -----------------------------------------------------------------------------------

export function useReviewQueue(page: number, pageSize = 25) {
  return useQuery({
    queryKey: ["reviews", "queue", page, pageSize],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/reviews/queue", { params: { query: { page, page_size: pageSize } } }),
      ),
    placeholderData: keepPreviousData,
  });
}

export type ReviewStatus = "pending" | "approved" | "rejected";

export function useReviews(status: ReviewStatus | undefined, page: number, pageSize = 25) {
  return useQuery({
    queryKey: ["reviews", "list", status ?? null, page, pageSize],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/reviews", { params: { query: { status, page, page_size: pageSize } } }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useCreateReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      transaction_id: string;
      decision: "confirmed" | "false_positive";
      note?: string;
    }): Promise<Review> => unwrap(api.POST("/api/v1/reviews", { body })),
    onSuccess: () => invalidateActivity(client),
  });
}

export function useDecideReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: number;
      action: "approve" | "reject";
      note: string;
    }): Promise<Review> =>
      action === "approve"
        ? unwrap(
            api.POST("/api/v1/reviews/{review_id}/approve", {
              params: { path: { review_id: id } },
              body: { note },
            }),
          )
        : unwrap(
            api.POST("/api/v1/reviews/{review_id}/reject", {
              params: { path: { review_id: id } },
              body: { note },
            }),
          ),
    onSuccess: () => invalidateActivity(client),
  });
}

export function useBulkApprove() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { review_ids: number[]; note?: string }): Promise<BulkApproveResult> =>
      unwrap(api.POST("/api/v1/reviews/bulk-approve", { body })),
    onSuccess: () => invalidateActivity(client),
  });
}

// Models ------------------------------------------------------------------------------------

export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: () => unwrap(api.GET("/api/v1/models")),
  });
}

export function useModelEvaluation(versionId: number | undefined) {
  return useQuery({
    queryKey: ["models", "evaluation", versionId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/models/{version_id}/evaluation", {
          params: { path: { version_id: versionId! } },
        }),
      ),
    enabled: versionId !== undefined,
  });
}

export function useActivateModel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (versionId: number) =>
      unwrap(
        api.POST("/api/v1/models/{version_id}/activate", {
          params: { path: { version_id: versionId } },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["models"] }),
  });
}

export function useSyncModels() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/models/sync")),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["models"] }),
  });
}

// Ingestion ---------------------------------------------------------------------------------

const RUNNING = new Set(["queued", "running"]);

export function useBatches(page: number, pageSize = 20) {
  const client = useQueryClient();
  return useQuery({
    queryKey: ["batches", page, pageSize],
    queryFn: async ({ queryKey }) => {
      const before = client.getQueryData<Page<Batch>>(queryKey);
      const data = await unwrap(
        api.GET("/api/v1/ingestion/batches", { params: { query: { page, page_size: pageSize } } }),
      );
      // A load that just finished changed the transactions, so refresh everything that shows them.
      const wasRunning = new Set(before?.items.filter(isRunning).map((batch) => batch.id));
      if (data.items.some((batch) => wasRunning.has(batch.id) && !isRunning(batch))) {
        invalidateActivity(client);
      }
      return data;
    },
    placeholderData: keepPreviousData,
    // Poll while a load is in progress.
    refetchInterval: (query) =>
      query.state.data?.items.some((batch) => RUNNING.has(batch.status)) ? 2000 : false,
  });
}

export function isRunning(batch: Batch) {
  return RUNNING.has(batch.status);
}

export function useUploadMonth() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (form: FormData): Promise<Batch> => {
      const response = await apiFetch("/api/v1/ingestion/upload", { method: "POST", body: form });
      return (await response.json()) as Batch;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["batches"] });
      invalidateActivity(client);
    },
  });
}

// Users and audit ---------------------------------------------------------------------------

export function useUsers({ enabled = true } = {}) {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => unwrap(api.GET("/api/v1/users")),
    enabled,
  });
}

export function useCreateUser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; full_name?: string; password: string; role: Role }) =>
      unwrap(api.POST("/api/v1/users", { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      full_name?: string;
      role?: Role;
      is_active?: boolean;
      password?: string;
    }) => unwrap(api.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: id } }, body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["users"] }),
  });
}

export interface AuditFilters {
  entity?: string;
  entity_id?: string;
  action?: string;
}

export function useAudit(filters: AuditFilters, page: number, pageSize = 50) {
  return useQuery({
    queryKey: ["audit", filters, page, pageSize],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/audit", { params: { query: { ...filters, page, page_size: pageSize } } }),
      ),
    placeholderData: keepPreviousData,
  });
}
