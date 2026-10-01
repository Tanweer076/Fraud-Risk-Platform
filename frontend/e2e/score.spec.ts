import { expect, stateFile, test } from "./support";

test.use({ storageState: stateFile("analyst") });

test("scores a transaction whose amounts differ, explains it and opens it", async ({ page }) => {
  await page.goto("/score");
  await page.getByLabel("Fill with an example").selectOption({ label: "FA amount differs" });
  await page.getByRole("button", { name: "Score transaction" }).click();

  // An amount mismatch is a break, so the rule floor puts the score at 70 (high) or above.
  const meter = page.getByRole("meter");
  await expect(meter).toHaveAttribute("aria-valuetext", /^\d+ out of 100, (High|Critical) risk$/);
  const score = (await meter.getAttribute("aria-valuenow"))!;
  expect(Number(score)).toBeGreaterThanOrEqual(70);

  const checks = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Checks that failed" }),
  });
  await expect(checks.getByRole("listitem").filter({ hasText: /amount/i })).not.toHaveCount(0);
  const reasons = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Why the model scored it this way" }),
  });
  await expect(reasons).toBeVisible();

  const title = await page.getByRole("heading", { name: /^Transaction / }).textContent();
  const transactionId = title!.replace("Transaction ", "");
  await page.getByRole("link", { name: "Open and review" }).click();
  await expect(page.getByRole("heading", { level: 1, name: transactionId })).toBeVisible();
  // The stored transaction carries the score it was given.
  await expect(page.getByRole("meter")).toHaveAttribute("aria-valuenow", score);
});

test("finds no breaks when all three systems agree", async ({ page }) => {
  await page.goto("/score");
  await page.getByLabel("Fill with an example").selectOption({ label: "All three systems agree" });
  await page.getByRole("button", { name: "Score transaction" }).click();
  await expect(page.getByRole("meter")).toBeVisible();
  await expect(page.getByText("No breaks: the systems agree and every rule passes.")).toBeVisible();
});
