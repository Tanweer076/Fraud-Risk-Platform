import { randomBytes } from "node:crypto";
import { expect, stateFile, test } from "./support";

test.use({ storageState: stateFile("admin") });

const SIGNED_OUT = { cookies: [], origins: [] };

test("an admin adds a user who can sign in, then deactivates them", async ({
  page,
  browser,
  baseURL,
}) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = randomBytes(18).toString("base64url");

  await page.goto("/admin");
  const form = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Add a user" }),
  });
  await form.getByLabel("Email").fill(email);
  await form.getByLabel("Full name").fill("E2E New Approver");
  await form.getByLabel("Role").selectOption("approver");
  await form.getByLabel("Password").fill(password);
  await form.getByRole("button", { name: "Add user" }).click();
  await expect(page.getByText(`Added ${email} as approver.`)).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row).toContainText("Active");

  // The new user signs in, in a browser of their own, and gets an approver's menu.
  const context = await browser.newContext({ baseURL, storageState: SIGNED_OUT });
  const newcomer = await context.newPage();
  await newcomer.goto("/");
  await newcomer.getByLabel("Email").fill(email);
  await newcomer.getByLabel("Password").fill(password);
  await newcomer.getByRole("button", { name: "Sign in" }).click();
  const nav = newcomer.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Admin" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Score transaction" })).toHaveCount(0);

  // Deactivating ends their session at their next request.
  await row.getByRole("button", { name: "Deactivate" }).click();
  await expect(row).toContainText("Deactivated");
  await nav.getByRole("link", { name: "Transactions" }).click();
  await expect(newcomer.getByText("Your session ended. Sign in again to continue.")).toBeVisible();
  await context.close();
});
