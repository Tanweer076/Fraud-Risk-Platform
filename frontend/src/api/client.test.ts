import { expect, it } from "vitest";
import { errorMessage } from "./client";

it("uses FastAPI's message", () => {
  expect(errorMessage(409, { detail: "Review 3 is already approved" })).toBe(
    "Review 3 is already approved",
  );
});

it("turns validation errors into field messages", () => {
  const body = {
    detail: [
      { loc: ["body", "amount"], msg: "Input should be a valid number" },
      { loc: ["query", "period"], msg: "String should match pattern" },
    ],
  };
  expect(errorMessage(422, body)).toBe(
    "amount: Input should be a valid number; period: String should match pattern",
  );
});

it("falls back to a generic message", () => {
  expect(errorMessage(502, null)).toBe("The server had a problem. Try again in a moment.");
  expect(errorMessage(404, "<html>")).toBe("Request failed (404)");
});
