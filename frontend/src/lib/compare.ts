import type { SystemCode, SystemRecord, TransactionDetail } from "../api/client";

export const SYSTEMS: SystemCode[] = ["gl", "ma", "fa"];

export type FieldKey = keyof SystemRecord;

export const FIELDS: { key: FieldKey; label: string }[] = [
  { key: "account_key", label: "Account key" },
  { key: "transaction_date", label: "Date" },
  { key: "amount", label: "Amount" },
  { key: "currency", label: "Currency" },
  { key: "country", label: "Country" },
  { key: "description", label: "Description" },
];

function comparable(key: FieldKey, record: SystemRecord): string | null {
  const value = record[key];
  if (value == null) return null;
  if (key === "amount") return Number(value).toFixed(2);
  if (key === "currency" || key === "country") return String(value).toUpperCase();
  return String(value);
}

/**
 * Which systems disagree on a field: those that differ from the value most systems hold (or all
 * of them, when no value has a majority). Account keys are checked against the join map instead,
 * since each system uses its own key format.
 */
export function mismatches(tx: TransactionDetail, key: FieldKey): Set<SystemCode> {
  const out = new Set<SystemCode>();
  if (key === "account_key") {
    const expected: Partial<Record<SystemCode, string | null>> = {
      ma: tx.expected_ma_key,
      fa: tx.expected_fa_key,
    };
    if (tx.systems.gl && !tx.gl_account_mapped) out.add("gl");
    for (const s of ["ma", "fa"] as const) {
      const record = tx.systems[s];
      if (record && expected[s] && record.account_key !== expected[s]) out.add(s);
    }
    return out;
  }
  const present = SYSTEMS.filter((s) => tx.systems[s]);
  const values = present.map((s) => comparable(key, tx.systems[s]!));
  const counts = new Map<string | null, number>();
  values.forEach((v) => counts.set(v, (counts.get(v) ?? 0) + 1));
  if (counts.size <= 1) return out;
  const [top, topCount] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  const majority = topCount > present.length / 2 ? top : undefined;
  present.forEach((s, i) => {
    if (majority === undefined || values[i] !== majority) out.add(s);
  });
  return out;
}
