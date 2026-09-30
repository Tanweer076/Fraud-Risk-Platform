import { expect, it } from "vitest";
import type { SystemRecord, TransactionDetail } from "../api/client";
import { mismatches } from "./compare";
import { transaction } from "../test/fixtures";

function record(overrides: Partial<SystemRecord> = {}): SystemRecord {
  return {
    account_key: "ACC0042",
    transaction_date: "2026-08-14",
    amount: 48200,
    currency: "USD",
    country: "US",
    description: "Vendor payment",
    rule_violations: null,
    ...overrides,
  };
}

function detail(systems: TransactionDetail["systems"], overrides: Partial<TransactionDetail> = {}) {
  return {
    ...transaction(),
    systems,
    expected_ma_key: "CUS-000042",
    expected_fa_key: "FA-000042",
    gl_account_mapped: true,
    predictions: [],
    reviews: [],
    ...overrides,
  } as TransactionDetail;
}

it("flags the system that disagrees with the majority", () => {
  const tx = detail({
    gl: record(),
    ma: record({ account_key: "CUS-000042" }),
    fa: record({ account_key: "FA-000042", amount: 4820 }),
  });
  expect([...mismatches(tx, "amount")]).toEqual(["fa"]);
  expect(mismatches(tx, "currency").size).toBe(0);
});

it("treats 48200 and 48200.00 as equal, and currency case as equal", () => {
  const tx = detail({ gl: record({ amount: 48200.0 }), fa: record({ currency: "usd" }) });
  expect(mismatches(tx, "amount").size).toBe(0);
  expect(mismatches(tx, "currency").size).toBe(0);
});

it("marks both systems when two disagree and neither is the majority", () => {
  const tx = detail({
    gl: record({ transaction_date: "2026-08-14" }),
    ma: record({ transaction_date: "2026-08-16" }),
  });
  expect([...mismatches(tx, "transaction_date")].sort()).toEqual(["gl", "ma"]);
});

it("checks account keys against the join map", () => {
  const tx = detail(
    {
      gl: record(),
      ma: record({ account_key: "CUS-000099" }),
      fa: record({ account_key: "FA-000042" }),
    },
    { gl_account_mapped: false },
  );
  expect([...mismatches(tx, "account_key")].sort()).toEqual(["gl", "ma"]);
});
