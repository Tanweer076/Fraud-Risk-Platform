import { ADMIN, expect, test, TEST_USERS } from "./support";

test("signs in with an HttpOnly cookie that page scripts cannot read, then signs out", async ({
  page,
  context,
}) => {
  await page.goto("/transactions");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill(ADMIN.email);
  await page.getByLabel("Password").fill(ADMIN.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  // Back on the page the visitor asked for.
  await expect(page.getByRole("heading", { level: 1, name: "Transactions" })).toBeVisible();
  await expect(page).toHaveURL(/\/transactions$/);

  const cookie = (await context.cookies()).find((c) => c.name === "fraud_session");
  expect(cookie).toMatchObject({ httpOnly: true, sameSite: "Strict", path: "/api" });
  const readable = await page.evaluate(() => ({
    cookies: document.cookie,
    storage: JSON.stringify({ ...localStorage, ...sessionStorage }),
  }));
  expect(readable.cookies).not.toContain("fraud_session");
  expect(readable.storage).not.toContain(cookie!.value);

  // The session outlives a reload.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Transactions" })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect((await context.cookies()).map((c) => c.name)).not.toContain("fraud_session");
  expect((await page.request.get("/api/v1/auth/session")).status()).toBe(401);
});

test("refuses a wrong password", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_USERS.analyst.email);
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByText("That email and password don't match an active account."),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});
