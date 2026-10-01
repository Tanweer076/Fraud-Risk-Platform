/** Display formatting for numbers, money, dates and the labels the API sends as codes. */

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const usdCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const usdFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const moneyFormats = new Map<string, Intl.NumberFormat>();

export const DASH = "—";

export function formatNumber(value: number | null | undefined): string {
  return value == null ? DASH : integer.format(value);
}

/** 1,284 / 12.9K / 4.2M: for stat tiles and chart labels. */
export function formatCompact(value: number | null | undefined): string {
  if (value == null) return DASH;
  return Math.abs(value) < 10_000 ? integer.format(value) : compact.format(value);
}

export function formatUsd(value: number | null | undefined, { full = false } = {}): string {
  if (value == null) return DASH;
  if (full || Math.abs(value) < 10_000) return usdFull.format(value);
  return usdCompact.format(value);
}

/** An amount in its own currency. Unknown or malformed codes (bad source data) still display. */
export function formatMoney(value: number | null | undefined, currency: string | null | undefined) {
  if (value == null) return DASH;
  const code = (currency ?? "").toUpperCase();
  let format = moneyFormats.get(code);
  if (!format) {
    try {
      format = new Intl.NumberFormat("en-US", { style: "currency", currency: code });
    } catch {
      return `${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency ?? ""}`.trim();
    }
    moneyFormats.set(code, format);
  }
  return format.format(value);
}

/** A 0-1 rate as a percentage, with one decimal below 10%. */
export function formatPercent(rate: number | null | undefined): string {
  if (rate == null) return DASH;
  const pct = rate * 100;
  // Decide on the rounded value, so 9.99% reads "10%" like 10.01% does, not "10.0%".
  const rounded = Math.round(pct * 10) / 10;
  const digits = rounded !== 0 && Math.abs(rounded) < 10 ? 1 : 0;
  return `${pct.toFixed(digits)}%`;
}

const percentTick = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });

/** Rate axis ticks: 0%, 2.5%, 5%, with no trailing zeros. */
export function formatPercentTick(rate: number): string {
  return percentTick.format(rate);
}

/** Axis ticks: always compact (5.5K, 22K), so one axis never mixes styles. */
export function formatTick(value: number): string {
  return compact.format(value);
}

export function formatDecimal(value: number | null | undefined, digits = 3): string {
  return value == null ? DASH : value.toFixed(digits);
}

export function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : DASH;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return DASH;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** 950 ms / 12.4 s / 3 min 05 s. */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return DASH;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s`;
}

/** 512 B / 14.2 KB / 3.1 MB. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return DASH;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "202608" -> "Aug 2026". */
export function formatPeriod(period: string | null | undefined): string {
  if (!period || !/^\d{6}$/.test(period)) return period ?? DASH;
  const month = MONTHS[Number(period.slice(4)) - 1];
  return month ? `${month} ${period.slice(0, 4)}` : period;
}

const SYSTEM_NAMES: Record<string, string> = { gl: "GL", ma: "MA", fa: "FA" };

const BREAK_LABELS: Record<string, string> = {
  amount_mismatch: "Amount mismatch",
  date_mismatch: "Date mismatch",
  currency_mismatch: "Currency mismatch",
  unmapped_account: "Unmapped account",
  key_mismatch: "Key mismatch",
  rule_violation: "Rule violation",
};

/** "missing_in_gl" -> "Missing in GL", "amount_mismatch" -> "Amount mismatch". */
export function breakLabel(code: string): string {
  const missing = /^missing_in_(\w+)$/.exec(code);
  if (missing) return `Missing in ${SYSTEM_NAMES[missing[1]] ?? missing[1].toUpperCase()}`;
  return BREAK_LABELS[code] ?? sentenceCase(code);
}

export function systemName(code: string): string {
  return SYSTEM_NAMES[code] ?? code.toUpperCase();
}

/** "logistic_regression" -> "Logistic regression". */
export function sentenceCase(code: string): string {
  const text = code.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
