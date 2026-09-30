import { expect, it } from "vitest";
import { actionLabel, auditRecord, describeChanges, formatAuditValue } from "./audit";

it("lists only the fields an update changed", () => {
  const before = { email: "a@example.com", role: "analyst", is_active: true };
  const after = { email: "a@example.com", role: "approver", is_active: true, password: "changed" };
  expect(describeChanges(before, after)).toEqual([
    { field: "role", before: "analyst", after: "approver" },
    { field: "password", after: "changed" },
  ]);
});

it("lists everything a creation recorded", () => {
  expect(describeChanges(null, { decision: "confirmed", note: "" })).toEqual([
    { field: "decision", after: "confirmed" },
    { field: "note", after: "" },
  ]);
  expect(describeChanges(null, null)).toEqual([]);
});

it("formats values for reading", () => {
  expect(formatAuditValue(null)).toBe("none");
  expect(formatAuditValue(["gl", "fa"])).toBe("gl, fa");
  expect(formatAuditValue({ a: 1 })).toBe('{"a":1}');
  expect(formatAuditValue("")).toBe('""');
});

it("links records to where they are shown", () => {
  expect(auditRecord("transaction", "ABC 1")).toEqual({
    label: "ABC 1",
    href: "/transactions/ABC%201",
  });
  expect(auditRecord("model_version", "2").href).toBe("/models?version=2");
  expect(auditRecord("review", "5")).toEqual({ label: "Review 5" });
  expect(actionLabel("review.approve")).toBe("Approved a finding");
  expect(actionLabel("unknown.action")).toBe("unknown.action");
});
