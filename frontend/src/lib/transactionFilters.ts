import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import type { TransactionFilters } from "../api/queries";
import { isBand } from "./bands";

export const BREAK_TYPES = [
  "amount_mismatch",
  "date_mismatch",
  "currency_mismatch",
  "missing_in_gl",
  "missing_in_ma",
  "missing_in_fa",
  "unmapped_account",
  "key_mismatch",
  "rule_violation",
];

export const DEFAULT_SORT = "-priority,-risk_score,-exposure_usd";

const TEXT_KEYS = [
  "period",
  "break_type",
  "currency",
  "country",
  "account",
  "date_from",
  "date_to",
  "search",
] as const;

function parseBool(value: string | null): boolean | undefined {
  return value === "true" ? true : value === "false" ? false : undefined;
}

function parseScore(value: string | null): number | undefined {
  if (value === null || value === "") return undefined;
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 && n <= 100 ? n : undefined;
}

export function parseFilters(params: URLSearchParams): TransactionFilters {
  const filters: TransactionFilters = {};
  for (const key of TEXT_KEYS) {
    const value = params.get(key)?.trim();
    if (value) filters[key] = value;
  }
  const bands = params.getAll("band").filter(isBand);
  if (bands.length) filters.band = bands;
  filters.min_score = parseScore(params.get("min_score"));
  filters.max_score = parseScore(params.get("max_score"));
  filters.suspicious = parseBool(params.get("suspicious"));
  filters.reviewed = parseBool(params.get("reviewed"));
  for (const key of Object.keys(filters) as (keyof TransactionFilters)[]) {
    if (filters[key] === undefined) delete filters[key];
  }
  return filters;
}

type Patch = Partial<Record<keyof TransactionFilters | "sort" | "page", unknown>>;

/** Transaction list filters, sort and page, kept in the URL so views can be linked and reloaded. */
export function useTransactionFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(params), [params]);
  const sort = params.get("sort") || DEFAULT_SORT;
  const page = Math.max(1, Math.floor(Number(params.get("page"))) || 1);

  const update = useCallback(
    (patch: Patch) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(patch)) {
          next.delete(key);
          if (Array.isArray(value)) value.forEach((item) => next.append(key, String(item)));
          else if (value !== undefined && value !== null && value !== "")
            next.set(key, String(value));
        }
        // Any change other than paging starts again from the first page.
        if (!("page" in patch)) next.delete("page");
        return next;
      });
    },
    [setParams],
  );

  const clear = useCallback(() => setParams(new URLSearchParams()), [setParams]);

  return { filters, sort, page, update, clear, active: Object.keys(filters).length > 0 };
}

/** A link into the transaction list with these filters. */
export function transactionsLink(
  filters: Record<string, string | number | boolean | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `/transactions?${query}` : "/transactions";
}
