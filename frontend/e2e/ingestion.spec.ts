import { expect, stateFile, test } from "./support";

test.use({ storageState: stateFile("analyst") });

test("the load history lists the loaded months and links to their breaks", async ({ page }) => {
  await page.goto("/ingestion");
  const history = page.getByRole("table", { name: "Load history, newest first" });
  const loaded = history.locator("tbody > tr").filter({ hasText: "Loaded" });
  // The demo job loads three months.
  await expect(loaded.nth(2)).toBeVisible();

  await loaded.first().locator("td:nth-child(7)").getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1, name: "Transactions" })).toBeVisible();
  await expect(page).toHaveURL(/period=\d{6}.*suspicious=true|suspicious=true.*period=\d{6}/);
});
