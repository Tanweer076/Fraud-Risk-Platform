import { expect, stateFile, test, TEST_USERS } from "./support";

test.use({ storageState: stateFile("analyst") });

test("an analyst's finding waits for an approver, who approves it", async ({ page, openAs }) => {
  // The analyst takes the top of the queue.
  await page.goto("/reviews");
  const queue = page.getByRole("table", { name: /Flagged transactions without a finding/ });
  const first = queue.getByRole("row").nth(1);
  const transactionId = (await first.getByRole("link").textContent())!;
  await first.getByRole("button", { name: "Review" }).click();
  await page.getByRole("radio", { name: "Confirmed break" }).check();
  await page.getByLabel("Note (optional)").fill("End-to-end test: FA amount checked by hand.");
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await expect(queue.getByRole("link", { name: transactionId, exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Awaiting approval" }).click();
  await expect(page.getByRole("row").filter({ hasText: transactionId })).toContainText(
    TEST_USERS.analyst.email,
  );

  // The approver approves it.
  const approver = await openAs("approver");
  await approver.goto("/reviews?tab=pending");
  const pending = approver.getByRole("row").filter({ hasText: transactionId });
  await pending.getByRole("button", { name: "Decide" }).click();
  await approver.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(pending).toHaveCount(0);

  await approver.getByRole("button", { name: "Approved", exact: true }).click();
  const approved = approver.getByRole("row").filter({ hasText: transactionId });
  await expect(approved).toContainText("Confirmed break");
  await expect(approved).toContainText(TEST_USERS.approver.email);

  // The transaction shows the outcome.
  await approver.getByRole("link", { name: transactionId, exact: true }).click();
  await expect(approver.getByRole("heading", { level: 1, name: transactionId })).toBeVisible();
  await expect(approver.getByText(`Approved by ${TEST_USERS.approver.email}`)).toBeVisible();
});

test("an approver rejects a finding only with a reason", async ({ page, openAs }) => {
  await page.goto("/reviews");
  const first = page.getByRole("row").nth(1);
  const transactionId = (await first.getByRole("link").textContent())!;
  await first.getByRole("button", { name: "Review" }).click();
  await page.getByRole("radio", { name: "False positive" }).check();
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await expect(page.getByRole("link", { name: transactionId, exact: true })).toHaveCount(0);

  const approver = await openAs("approver");
  await approver.goto("/reviews?tab=pending");
  await approver
    .getByRole("row")
    .filter({ hasText: transactionId })
    .getByRole("button", { name: "Decide" })
    .click();
  await approver.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(approver.getByText("Say why you are rejecting it.")).toBeVisible();
  await approver
    .getByLabel("Approver note (required to reject)")
    .fill("The FA amount was keyed wrong; it is a real break.");
  await approver.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(approver.getByRole("row").filter({ hasText: transactionId })).toHaveCount(0);

  await approver.getByRole("button", { name: "Rejected", exact: true }).click();
  await expect(approver.getByRole("row").filter({ hasText: transactionId })).toContainText(
    "The FA amount was keyed wrong",
  );
});
