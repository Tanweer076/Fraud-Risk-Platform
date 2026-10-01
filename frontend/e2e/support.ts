import path from "node:path";
import { type BrowserContext, type Page, test as base, expect } from "@playwright/test";

export type Role = "admin" | "analyst" | "approver";

/** The admin the seed or demo job created, from ADMIN_EMAIL and ADMIN_PASSWORD. */
export const ADMIN = {
  email: process.env.ADMIN_EMAIL || "admin@example.com",
  password: process.env.ADMIN_PASSWORD ?? "",
};

/** Users the setup adds (or resets) with a fresh random password on every run. */
export const TEST_USERS = {
  analyst: { email: "e2e-analyst@example.com", full_name: "E2E Analyst" },
  approver: { email: "e2e-approver@example.com", full_name: "E2E Approver" },
} as const;

/** The signed-in browser state for a role, written by auth.setup.ts. */
export const stateFile = (role: Role) => path.join(import.meta.dirname, ".auth", `${role}.json`);

/** The dashboard's own header on cookie-authenticated writes (the API's CSRF check). */
export const CSRF = { "X-Requested-With": "fetch" };

/**
 * Collect what the page logs as errors: uncaught exceptions, React errors and
 * Content-Security-Policy violations. Failed requests are left to the tests' assertions.
 */
function collectErrors(page: Page, errors: string[]) {
  page.on("pageerror", (error) => errors.push(`Uncaught: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource")) {
      errors.push(message.text());
    }
  });
}

export const test = base.extend<{
  browserErrors: string[];
  openAs: (role: Role) => Promise<Page>;
}>({
  // Every test fails if a page it opened logged an error.
  browserErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      collectErrors(page, errors);
      await use(errors);
      expect(errors, "errors logged in the browser").toEqual([]);
    },
    { auto: true },
  ],
  /** A second signed-in user in the same test, in a browser context of their own. */
  openAs: async ({ browser, baseURL, browserErrors }, use) => {
    const opened: BrowserContext[] = [];
    await use(async (role) => {
      const context = await browser.newContext({ baseURL, storageState: stateFile(role) });
      opened.push(context);
      const page = await context.newPage();
      collectErrors(page, browserErrors);
      return page;
    });
    await Promise.all(opened.map((context) => context.close()));
  },
});

export { expect };
