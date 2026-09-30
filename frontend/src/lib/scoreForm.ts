/** The Score page's form: values, validation, examples and the API request they become. */
import { z } from "zod";
import type { PredictionRequest, RecordIn, SystemCode } from "../api/client";

export const SYSTEMS: SystemCode[] = ["gl", "ma", "fa"];

export const KEY_LABEL: Record<SystemCode, { label: string; placeholder: string }> = {
  gl: { label: "GL account", placeholder: "ACC0001" },
  ma: { label: "MA customer key", placeholder: "CUS-000001" },
  fa: { label: "FA key", placeholder: "FA-000001" },
};

// Suggestions from the business rules; other values are allowed and scored as rule breaches.
export const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "CAD", "CHF", "AUD"];
export const COUNTRIES = ["US", "GB", "DE", "FR", "IN", "JP", "CH", "AU", "CA", "SG", "HK"];

const recordFields = z.object({
  account_key: z.string(),
  transaction_date: z.string(),
  amount: z.string(),
  currency: z.string(),
  country: z.string(),
  description: z.string(),
});

const recordRules = z.object({
  account_key: z.string().trim().min(1, "Enter the key").max(64, "Up to 64 characters"),
  transaction_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Enter a date"),
  amount: z
    .string()
    .trim()
    .min(1, "Enter an amount")
    .refine((value) => Number.isFinite(Number(value)), "Enter a number"),
  currency: z.string().trim().min(1, "Enter a currency").max(8, "Up to 8 characters"),
  country: z.string().trim().min(1, "Enter a country").max(8, "Up to 8 characters"),
  description: z.string().trim().max(255, "Up to 255 characters"),
});

export const scoreFormSchema = z
  .object({
    transaction_id: z
      .string()
      .trim()
      .regex(/^[A-Za-z0-9_-]{0,64}$/, "Use letters, digits, - and _ (up to 64)"),
    source_system: z.enum(["gl", "ma", "fa"]),
    include: z.object({ gl: z.boolean(), ma: z.boolean(), fa: z.boolean() }),
    records: z.object({ gl: recordFields, ma: recordFields, fa: recordFields }),
  })
  .superRefine((values, ctx) => {
    // Only the records being sent are checked: the source system's and included counterparts.
    for (const system of SYSTEMS) {
      if (system !== values.source_system && !values.include[system]) continue;
      const result = recordRules.safeParse(values.records[system]);
      if (result.success) continue;
      for (const issue of result.error.issues) {
        ctx.addIssue({
          code: "custom",
          message: issue.message,
          path: ["records", system, ...issue.path],
        });
      }
    }
  });

export type ScoreFormValues = z.infer<typeof scoreFormSchema>;
export type RecordValues = ScoreFormValues["records"]["gl"];

const BLANK: RecordValues = {
  account_key: "",
  transaction_date: "",
  amount: "",
  currency: "USD",
  country: "US",
  description: "",
};

export const SCORE_FORM_DEFAULTS: ScoreFormValues = {
  transaction_id: "",
  source_system: "gl",
  include: { gl: false, ma: false, fa: false },
  records: { gl: { ...BLANK }, ma: { ...BLANK }, fa: { ...BLANK } },
};

const MATCHED = {
  transaction_date: "2026-08-14",
  amount: "1250.00",
  currency: "USD",
  country: "US",
  description: "Vendor payment",
};

/** Ready-made submissions for the account the join map links as ACC0001 / CUS-000001 / FA-000001. */
export const EXAMPLES: { label: string; values: ScoreFormValues }[] = [
  {
    label: "All three systems agree",
    values: {
      ...SCORE_FORM_DEFAULTS,
      include: { gl: false, ma: true, fa: true },
      records: {
        gl: { ...MATCHED, account_key: "ACC0001" },
        ma: { ...MATCHED, account_key: "CUS-000001" },
        fa: { ...MATCHED, account_key: "FA-000001" },
      },
    },
  },
  {
    label: "FA amount differs",
    values: {
      ...SCORE_FORM_DEFAULTS,
      include: { gl: false, ma: true, fa: true },
      records: {
        gl: { ...MATCHED, account_key: "ACC0001", amount: "48200.00" },
        ma: { ...MATCHED, account_key: "CUS-000001", amount: "48200.00" },
        fa: { ...MATCHED, account_key: "FA-000001", amount: "4820.00" },
      },
    },
  },
  {
    label: "Missing in MA",
    values: {
      ...SCORE_FORM_DEFAULTS,
      include: { gl: false, ma: false, fa: true },
      records: {
        gl: { ...MATCHED, account_key: "ACC0001" },
        ma: { ...BLANK },
        fa: { ...MATCHED, account_key: "FA-000001" },
      },
    },
  },
  {
    label: "Breaks a business rule",
    values: {
      ...SCORE_FORM_DEFAULTS,
      include: { gl: false, ma: true, fa: true },
      records: {
        gl: { ...MATCHED, account_key: "ACC0001", amount: "250000.00" },
        ma: { ...MATCHED, account_key: "CUS-000001", amount: "250000.00" },
        fa: { ...MATCHED, account_key: "FA-000001", amount: "250000.00" },
      },
    },
  },
];

function toRecord(values: RecordValues): RecordIn {
  return {
    account_key: values.account_key.trim(),
    transaction_date: values.transaction_date,
    amount: Number(values.amount),
    currency: values.currency.trim().toUpperCase(),
    country: values.country.trim().toUpperCase(),
    description: values.description.trim(),
  };
}

/** The POST /predictions body: the source record plus the included counterparts. */
export function toRequest(values: ScoreFormValues): PredictionRequest {
  const source = values.source_system;
  const counterparts: PredictionRequest["counterparts"] = {};
  for (const system of SYSTEMS) {
    if (system !== source && values.include[system]) {
      counterparts[system] = toRecord(values.records[system]);
    }
  }
  return {
    ...toRecord(values.records[source]),
    transaction_id: values.transaction_id.trim() || undefined,
    source_system: source,
    counterparts,
  };
}
