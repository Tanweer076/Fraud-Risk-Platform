import { expect, type Role, stateFile, test } from "./support";

// Each role's menu, and the heading each page opens with.
const PAGES: { link: string; heading: string; roles: Role[] }[] = [
  { link: "Dashboard", heading: "Dashboard", roles: ["admin", "analyst", "approver"] },
  { link: "Score transaction", heading: "Score a transaction", roles: ["admin", "analyst"] },
  { link: "Transactions", heading: "Transactions", roles: ["admin", "analyst", "approver"] },
  { link: "Review queue", heading: "Review queue", roles: ["admin", "analyst", "approver"] },
  { link: "Analytics", heading: "Analytics", roles: ["admin", "analyst", "approver"] },
  { link: "Models", heading: "Models", roles: ["admin", "analyst", "approver"] },
  { link: "Data ingestion", heading: "Data ingestion", roles: ["admin", "analyst", "approver"] },
  { link: "Admin", heading: "Admin", roles: ["admin", "approver"] },
];

for (const role of ["admin", "analyst", "approver"] as const) {
  test.describe(`as ${role}`, () => {
    test.use({ storageState: stateFile(role) });

    test("every page in the menu opens", async ({ page }) => {
      await page.goto("/");
      const nav = page.getByRole("navigation", { name: "Main" });
      await expect(nav.getByRole("link")).toHaveText(
        PAGES.filter((p) => p.roles.includes(role)).map((p) => p.link),
      );
      for (const { link, heading } of PAGES.filter((p) => p.roles.includes(role))) {
        await nav.getByRole("link", { name: link, exact: true }).click();
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        // Wait for the page's data, so a failed request or a render error shows up here.
        await expect(page.getByText(/^Loading.*…$/)).toHaveCount(0);
        await expect(page.getByRole("alert")).toHaveCount(0);
      }
    });
  });
}
