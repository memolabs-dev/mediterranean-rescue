import { expect, test } from "@playwright/test";

test("an HTML gateway failure shows retry rather than crashing the public site", async ({ page }) => {
  let failing = true;
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/events/" && failing) {
      await route.fulfill({ status: 502, contentType: "text/html", body: "<html><h1>Bad gateway</h1></html>" });
      return;
    }
    const body = path === "/api/v1/events/"
      ? { items: [], total_count: 0, has_next: false, data_mode: "production" }
      : path === "/api/v1/map-points/"
        ? { points: [], located_count: 0, truncated: false }
        : path === "/api/private/v1/session/"
          ? { signed_in: false, local_auto_login: false }
          : null;
    await route.fulfill({ status: body ? 200 : 404, contentType: "application/json", body: JSON.stringify(body ?? { code: "not_found" }) });
  });
  await page.goto("/");
  await expect(page.getByText("Loading the data failed. Earlier results may be out of date.")).toBeVisible({ timeout: 16000 });
  await expect(page.getByText("Something went wrong on this page. Reload it to continue.")).toHaveCount(0);
  failing = false;
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("Nothing published yet")).toBeVisible({ timeout: 12000 });
});
