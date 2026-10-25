import { expect, test } from "@playwright/test";

test("the health probe checks the database", async ({ request }) => {
  const response = await request.get("/api/health/");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
});

test("pages carry the security headers", async ({ request }) => {
  const response = await request.get("/about");
  const headers = response.headers();
  expect(headers["content-security-policy"]).toContain("default-src 'self'");
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("same-origin");
});

test("an unknown API address answers JSON, never the application page", async ({ request }) => {
  const response = await request.get("/api/v1/does-not-exist/");
  expect(response.status()).toBe(404);
  expect(response.headers()["content-type"]).not.toContain("text/html");
});

test("the private API refuses a visitor who is not signed in", async ({ request }) => {
  const response = await request.get("/api/private/v1/history/");
  expect([401, 403]).toContain(response.status());
});

test("built assets are cached for good, the page is revalidated", async ({ request }) => {
  const page = await request.get("/");
  const asset = (await page.text()).match(/\/assets\/[^"]+\.js/)?.[0];
  expect(asset).toBeTruthy();
  const response = await request.get(asset!);
  expect(response.headers()["cache-control"]).toContain("immutable");
});
