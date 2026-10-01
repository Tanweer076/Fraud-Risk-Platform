/**
 * Typed API client. Types come from the backend's OpenAPI schema (npm run gen:api), so a
 * renamed field fails the type check instead of rendering blank.
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

type Schemas = components["schemas"];
export type Band = "low" | "medium" | "high" | "critical";
export type Role = Schemas["UserOut"]["role"];
export type SystemCode = "gl" | "ma" | "fa";
export type User = Schemas["UserOut"];
export type Token = Schemas["Token"];
export type TransactionSummary = Schemas["TransactionSummary"];
export type TransactionDetail = Schemas["TransactionDetail"];
export type SystemRecord = Schemas["SystemRecordOut"];
export type Prediction = Schemas["PredictionOut"];
export type PredictionRequest = Schemas["PredictionRequest"];
export type RecordIn = Schemas["RecordIn"];
export type ScoreResult = Schemas["ScoreResult"];
export type Factor = Schemas["Factor"];
export type RuleHit = Schemas["RuleHit"];
export type Review = Schemas["ReviewOut"];
export type Summary = Schemas["Summary"];
export type RiskDistribution = Schemas["RiskDistribution"];
export type TrendPoint = Schemas["TrendPoint"];
export type BreakdownRow = Schemas["BreakdownRow"];
export type TopAccount = Schemas["TopAccount"];
export type ModelVersion = Schemas["ModelVersionOut"];
export type ModelEvaluation = Schemas["ModelEvaluation"];
export type Batch = Schemas["BatchOut"];
export type AuditEntry = Schemas["AuditOut"];
export type BulkApproveResult = Schemas["BulkApproveResult"];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** An error response from the API, with FastAPI's `detail` turned into one readable message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // 422: [{loc: ["body", "amount"], msg: "..."}]
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = (d.loc ?? []).filter((part) => part !== "body" && part !== "query").join(".");
        return field ? `${field}: ${d.msg}` : (d.msg ?? "");
      })
      .join("; ");
  }
  if (status >= 500) return "The server had a problem. Try again in a moment.";
  return `Request failed (${status})`;
}

let authToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

/** Called when the API rejects the saved token (expired or revoked). */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

const auth: Middleware = {
  onRequest({ request }) {
    if (authToken) request.headers.set("Authorization", `Bearer ${authToken}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401 && authToken) unauthorizedHandler?.();
    return response;
  },
};

export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "http://localhost",
  // Resolve fetch at call time, so tests can replace it.
  fetch: (request) => globalThis.fetch(request),
});
api.use(auth);

/** The data of an openapi-fetch result, or an ApiError. */
export async function unwrap<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await result;
  if (!response.ok || error !== undefined) {
    throw new ApiError(response.status, errorMessage(response.status, error));
  }
  return data as T;
}

/** fetch for the calls openapi-fetch doesn't fit (form login, file upload, file download). */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const response = await globalThis.fetch(path, { ...init, headers });
  if (response.status === 401 && authToken) unauthorizedHandler?.();
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(response.status, body));
  }
  return response;
}
