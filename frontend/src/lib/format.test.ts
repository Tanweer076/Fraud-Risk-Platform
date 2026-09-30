import { describe, expect, it } from "vitest";
import {
  breakLabel,
  DASH,
  formatBytes,
  formatCompact,
  formatDateTime,
  formatDuration,
  formatMoney,
  formatNumber,
  formatPercent,
  formatPeriod,
  formatTick,
  formatUsd,
  sentenceCase,
} from "./format";

describe("numbers", () => {
  it("shows a dash for missing values", () => {
    expect(formatNumber(null)).toBe(DASH);
    expect(formatCompact(undefined)).toBe(DASH);
    expect(formatUsd(null)).toBe(DASH);
    expect(formatPercent(null)).toBe(DASH);
  });

  it("keeps small counts exact and compacts large ones", () => {
    expect(formatNumber(22263)).toBe("22,263");
    expect(formatCompact(9999)).toBe("9,999");
    expect(formatCompact(22263)).toBe("22.3K");
    expect(formatTick(5500)).toBe("5.5K");
  });

  it("formats USD compactly above 10,000 unless asked for the full amount", () => {
    expect(formatUsd(1250)).toBe("$1,250.00");
    expect(formatUsd(48_200_000)).toBe("$48.2M");
    expect(formatUsd(48_200_000, { full: true })).toBe("$48,200,000.00");
  });

  it("formats amounts in their own currency and survives bad codes from source data", () => {
    expect(formatMoney(1250, "eur")).toBe("€1,250.00");
    expect(formatMoney(1250.5, "XX1")).toBe("1,250.50 XX1");
    expect(formatMoney(null, "USD")).toBe(DASH);
  });

  it("gives small rates one decimal", () => {
    expect(formatPercent(0.0943)).toBe("9.4%");
    expect(formatPercent(0.25)).toBe("25%");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(0.0999)).toBe("10%");
    expect(formatPercent(0.0994)).toBe("9.9%");
  });

  it("formats durations and sizes", () => {
    expect(formatDuration(950)).toBe("950 ms");
    expect(formatDuration(19_800)).toBe("19.8 s");
    expect(formatDuration(185_000)).toBe("3 min 05 s");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(14_540)).toBe("14.2 KB");
    expect(formatBytes(3.1 * 1024 ** 2)).toBe("3.1 MB");
  });
});

describe("dates and labels", () => {
  it("formats a timestamp in local time", () => {
    expect(formatDateTime("2026-08-14T09:05:00")).toBe("2026-08-14 09:05");
    expect(formatDateTime("not a date")).toBe("not a date");
  });

  it("names periods", () => {
    expect(formatPeriod("202608")).toBe("Aug 2026");
    expect(formatPeriod("202613")).toBe("202613");
  });

  it("labels break codes", () => {
    expect(breakLabel("missing_in_ma")).toBe("Missing in MA");
    expect(breakLabel("amount_mismatch")).toBe("Amount mismatch");
    expect(breakLabel("something_new")).toBe("Something new");
    expect(sentenceCase("logistic_regression")).toBe("Logistic regression");
  });
});
