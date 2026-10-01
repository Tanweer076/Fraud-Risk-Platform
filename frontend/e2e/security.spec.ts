import { CSRF, expect, stateFile, test } from "./support";

test("pages and scripts carry the security headers", async ({ request }) => {
  const page = await request.get("/");
  expect(page.headers()).toMatchObject({
    "content-security-policy": expect.stringContaining("default-src 'self'"),
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
  });
  const script = /<script type="module" crossorigin src="([^"]+)"/.exec(await page.text())![1];
  const asset = await request.get(script);
  expect(asset.headers()["cache-control"]).toContain("immutable");
  expect(asset.headers()["x-content-type-options"]).toBe("nosniff");
});

test("the API's metrics are not served to the public", async ({ request }) => {
  for (const path of ["/metrics", "/api/metrics", "/api/v1/metrics"]) {
    const response = await request.get(path);
    expect(await response.text(), path).not.toContain("http_requests_total");
  }
});

test.describe("with a session cookie", () => {
  test.use({ storageState: stateFile("analyst") });

  test("a write without the dashboard's header is refused", async ({ page }) => {
    const review = { transaction_id: "NOT-A-TRANSACTION", decision: "confirmed", note: "" };
    const refused = await page.request.post("/api/v1/reviews", { data: review });
    expect(refused.status()).toBe(403);
    // With the header the request gets through, to the missing transaction.
    const allowed = await page.request.post("/api/v1/reviews", { data: review, headers: CSRF });
    expect(allowed.status()).toBe(404);
  });
});
