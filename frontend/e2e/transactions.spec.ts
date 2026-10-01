import { readFile } from "node:fs/promises";
import { expect, stateFile, test } from "./support";

test.use({ storageState: stateFile("analyst") });

/** One CSV line's fields; enough for this file, whose quoted fields have no line breaks. */
const fields = (line: string) =>
  line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map((field) => field.replace(/^"|"$/g, ""));

test("filters transactions, opens one and exports the filtered list", async ({ page }) => {
  await page.goto("/transactions");
  const table = page.getByRole("table", { name: /^Transactions/ });
  await expect(table.getByRole("row")).not.toHaveCount(0);

  // The riskiest come first, so the low band replaces the whole first page.
  await page.getByRole("group", { name: "Risk band" }).getByRole("button", { name: "Low" }).click();
  await expect(page).toHaveURL(/band=low/);
  const rows = table.locator("tbody").getByRole("row");
  await expect(rows.first()).toBeVisible();
  await expect(rows.locator("td:nth-child(7)").filter({ hasNotText: /Low$/ })).toHaveCount(0);

  const transactionId = (await rows.first().getByRole("link").textContent())!;
  await rows.first().getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1, name: transactionId })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Records by system" })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/band=low/);

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^transactions_.*\.csv$/);
  const [header, ...records] = (await readFile(await file.path(), "utf8"))
    .trim()
    .split(/\r?\n/)
    .map(fields);
  expect(header.slice(0, 2)).toEqual(["transaction_id", "period"]);
  // The export holds the filtered transactions, the opened one among them.
  expect(records.map((record) => record[0])).toContain(transactionId);
  const band = header.indexOf("risk_band");
  expect(new Set(records.map((record) => record[band]))).toEqual(new Set(["low"]));
});
