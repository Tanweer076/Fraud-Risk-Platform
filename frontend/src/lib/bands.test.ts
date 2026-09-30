import { expect, it } from "vitest";
import { bandFor, isBand } from "./bands";

it("puts scores in the same bands as the model's scoring", () => {
  expect([0, 39, 40, 69, 70, 89, 90, 100].map(bandFor)).toEqual([
    "low",
    "low",
    "medium",
    "medium",
    "high",
    "high",
    "critical",
    "critical",
  ]);
});

it("recognises band names", () => {
  expect(isBand("high")).toBe(true);
  expect(isBand("severe")).toBe(false);
  expect(isBand(null)).toBe(false);
});
