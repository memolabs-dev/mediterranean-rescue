import { defineConfig, devices } from "@playwright/test";

// End-to-end smoke tests against a running instance: the production image in CI
// (E2E_BASE_URL=http://127.0.0.1:8000), or the public demo after a release.
export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    // Plain HTTP to a production container: say TLS ended at a proxy, as Traefik does.
    extraHTTPHeaders: process.env.E2E_FORWARDED_PROTO ? { "X-Forwarded-Proto": process.env.E2E_FORWARDED_PROTO } : {},
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "phone", use: { ...devices["iPhone 15"] } },
  ],
});
