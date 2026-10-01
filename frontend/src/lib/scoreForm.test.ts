import { describe, expect, it } from "vitest";
import { EXAMPLES, SCORE_FORM_DEFAULTS, scoreFormSchema, toRequest } from "./scoreForm";

describe("toRequest", () => {
  it("sends the source record and only the included counterparts", () => {
    const values = structuredClone(EXAMPLES[2].values); // Missing in MA
    const request = toRequest(values);
    expect(request.source_system).toBe("gl");
    expect(request.account_key).toBe("ACC0001");
    expect(request.amount).toBe(1250);
    expect(Object.keys(request.counterparts ?? {})).toEqual(["fa"]);
    expect(request.transaction_id).toBeUndefined();
  });

  it("uppercases currency and country and trims text", () => {
    const values = structuredClone(EXAMPLES[0].values);
    values.transaction_id = "  ABC-1  ";
    values.records.gl = {
      ...values.records.gl,
      currency: " eur ",
      country: "de",
      description: " Fee ",
    };
    const request = toRequest(values);
    expect(request).toMatchObject({
      transaction_id: "ABC-1",
      currency: "EUR",
      country: "DE",
      description: "Fee",
    });
  });
});

describe("scoreFormSchema", () => {
  it("accepts every example", () => {
    for (const example of EXAMPLES)
      expect(scoreFormSchema.safeParse(example.values).success).toBe(true);
  });

  it("checks the source record and included counterparts only", () => {
    const result = scoreFormSchema.safeParse(SCORE_FORM_DEFAULTS);
    expect(result.success).toBe(false);
    const paths = result.error!.issues.map((issue) => issue.path.join("."));
    expect(paths).toEqual(
      expect.arrayContaining([
        "records.gl.account_key",
        "records.gl.transaction_date",
        "records.gl.amount",
      ]),
    );
    expect(
      paths.some((path) => path.startsWith("records.ma") || path.startsWith("records.fa")),
    ).toBe(false);
  });

  it("rejects an amount that is not a number", () => {
    const values = structuredClone(EXAMPLES[0].values);
    values.records.gl.amount = "12,50";
    const result = scoreFormSchema.safeParse(values);
    expect(result.error?.issues[0]).toMatchObject({
      path: ["records", "gl", "amount"],
      message: "Enter a number",
    });
  });
});
