/** Sample API data shaped like the real responses (dev database, Aug 2026). */
import type {
  Batch,
  Review,
  RiskDistribution,
  ScoreResult,
  Summary,
  TransactionSummary,
  User,
} from "../api/client";

const created_at = "2026-09-01T10:00:00Z";

export const admin: User = {
  id: 1,
  email: "admin@example.com",
  full_name: "Ada Admin",
  role: "admin",
  is_active: true,
  created_at,
};

export const analyst: User = {
  id: 2,
  email: "analyst@example.com",
  full_name: "Ana Analyst",
  role: "analyst",
  is_active: true,
  created_at,
};

export const approver: User = {
  id: 3,
  email: "approver@example.com",
  full_name: "Abe Approver",
  role: "approver",
  is_active: true,
  created_at,
};

export const summary: Summary = {
  period: null,
  periods: ["202606", "202607", "202608"],
  transactions: 61074,
  suspicious: 2941,
  suspicious_rate: 0.0482,
  scored: 61074,
  avg_risk_score: 5.2,
  high_or_critical: 2941,
  exposure_usd_at_risk: 48_200_000,
  by_band: { low: 58133, high: 2100, critical: 841 },
  review_queue: 2941,
  pending_approval: 0,
  confirmed: 0,
  false_positive: 0,
};

export const distribution: RiskDistribution = {
  period: null,
  bins: [
    { score_from: 0, score_to: 9, count: 58133 },
    { score_from: 70, score_to: 79, count: 2100 },
    { score_from: 90, score_to: 100, count: 841 },
  ],
  bands: [
    { band: "low", count: 58133, share: 0.9518 },
    { band: "high", count: 2100, share: 0.0344 },
    { band: "critical", count: 841, share: 0.0138 },
  ],
};

export function transaction(overrides: Partial<TransactionSummary> = {}): TransactionSummary {
  return {
    transaction_id: "7C1D2E3F4A5B6C7D",
    period: "202608",
    gl_account_id: "ACC0042",
    transaction_date: "2026-08-14",
    amount: 48200,
    currency: "USD",
    country: "US",
    description: "Vendor payment",
    in_gl: true,
    in_ma: true,
    in_fa: true,
    break_types: ["amount_mismatch"],
    is_suspicious: true,
    risk_score: 70,
    risk_band: "high",
    priority: 56,
    exposure_usd: 48200,
    model_version: "model_v1",
    scored_at: "2026-09-30T20:00:00Z",
    review_outcome: null,
    source: "batch",
    ...overrides,
  };
}

export function review(overrides: Partial<Review> = {}): Review {
  return {
    id: 11,
    transaction_id: "7C1D2E3F4A5B6C7D",
    prediction_id: 5,
    decision: "confirmed",
    note: "FA keyed 4,820 instead of 48,200",
    status: "pending",
    analyst_id: analyst.id,
    analyst_email: analyst.email,
    approver_id: null,
    approver_email: null,
    approver_note: null,
    decided_at: null,
    created_at: "2026-09-30T20:05:00Z",
    ...overrides,
  };
}

export const scoreResult: ScoreResult = {
  id: 99,
  transaction_id: "SCORED0000000001",
  model_version: "model_v1",
  probability: 0.02,
  model_score: 2,
  risk_score: 70,
  risk_band: "high",
  priority: 58,
  exposure_usd: 48200,
  break_types: ["amount_mismatch"],
  rule_hits: [
    { break_type: "amount_mismatch", reason: "FA amount 4,820.00 differs from GL 48,200.00" },
  ],
  top_factors: [
    { reason: "Amounts differ across systems", features: ["amount_spread"], contribution: 2.1 },
  ],
  source: "api",
  latency_ms: 412,
  created_at: "2026-09-30T20:10:00Z",
  created: true,
  in_systems: ["gl", "ma", "fa"],
};

export function batch(overrides: Partial<Batch> = {}): Batch {
  return {
    id: 7,
    period: "202608",
    method: "file",
    status: "succeeded",
    files: {
      gl: "GL_202608.xml",
      fa: "FA_202608.csv",
      join_map: "join_map.txt",
      ma: "ma_server.py",
    },
    records: { gl: 22263, ma: 22190, fa: 22201, join_map: 120 },
    summary: { transactions: 22263, suspicious: 2100, suspicious_rate: 0.0943 },
    transactions_loaded: 22263,
    transactions_scored: 22263,
    error: null,
    duration_ms: 19800,
    created_by_id: analyst.id,
    created_at: "2026-09-30T19:00:00Z",
    started_at: "2026-09-30T19:00:01Z",
    finished_at: "2026-09-30T19:00:21Z",
    ...overrides,
  };
}
