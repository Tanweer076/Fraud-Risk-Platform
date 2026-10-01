import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive a real browser against the running Docker stack with the demo data
// loaded (make docker-up docker-demo, then make e2e). They sign in as the admin from the
// repository's .env, the same file docker compose reads; variables already set win.
try {
  process.loadEnvFile(new URL("../.env", import.meta.url));
} catch {
  // No .env: CI sets the variables itself.
}

const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${process.env.WEB_PORT || 8080}`;
// A Chromium build to use instead of the one `npx playwright install chromium` downloads.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "./e2e",
  // The tests share one database and change it (reviews, users), so they run one at a time.
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } },
      dependencies: ["setup"],
    },
  ],
});
