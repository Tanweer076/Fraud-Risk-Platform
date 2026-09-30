import type { Band } from "../api/client";

/** Risk bands, lowest first. Mirrors fraudml's scoring: low < 40, medium < 70, high < 90. */
export const BANDS: readonly Band[] = ["low", "medium", "high", "critical"];

export const BAND_MIN: Record<Band, number> = { low: 0, medium: 40, high: 70, critical: 90 };

export const BAND_LABEL: Record<Band, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

/** Bands wear the fixed status colours (good, warning, serious, critical), always with a label. */
export const BAND_COLOR: Record<Band, string> = {
  low: "var(--status-good)",
  medium: "var(--status-warning)",
  high: "var(--status-serious)",
  critical: "var(--status-critical)",
};

export function isBand(value: unknown): value is Band {
  return typeof value === "string" && (BANDS as readonly string[]).includes(value);
}

export function bandFor(score: number): Band {
  if (score >= BAND_MIN.critical) return "critical";
  if (score >= BAND_MIN.high) return "high";
  if (score >= BAND_MIN.medium) return "medium";
  return "low";
}
