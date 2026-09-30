import { expect, it } from "vitest";
import { parseFilters, transactionsLink } from "./transactionFilters";

it("reads filters from the URL and ignores values the API would reject", () => {
  const params = new URLSearchParams(
    "period=202608&band=high&band=bogus&band=critical&suspicious=true&reviewed=maybe&min_score=70&max_score=101&search=%20ACC%20",
  );
  expect(parseFilters(params)).toEqual({
    period: "202608",
    band: ["high", "critical"],
    suspicious: true,
    min_score: 70,
    search: "ACC",
  });
});

it("builds links into the list", () => {
  expect(transactionsLink({ period: "202608", suspicious: true, account: undefined })).toBe(
    "/transactions?period=202608&suspicious=true",
  );
  expect(transactionsLink({})).toBe("/transactions");
});
