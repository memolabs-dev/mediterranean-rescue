import { expect, test } from "@playwright/test";

test("one map renderer across desktop, phone, resize and collapse", async ({ page }) => {
  // A synthetic API keeps this renderer test independent of running a local backend.
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path === "/api/v1/events/"
      ? { items: [], has_next: false, total_count: 0, data_mode: "production" }
      : path === "/api/v1/map-points/"
        ? { points: [{ id: "00000000-0000-0000-0000-000000000001", longitude: 15, latitude: 35.5, kind: "rescue" }], located_count: 1, truncated: false }
        : path === "/api/private/v1/session/"
          ? { signed_in: false, local_auto_login: false }
          : null;
    await route.fulfill({ status: body ? 200 : 404, contentType: "application/json", body: JSON.stringify(body ?? { code: "not_found" }) });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const desktop = page.locator(".explore-map--side");
  const phone = page.locator(".explore-map--inline");
  await expect(desktop.locator(".map-card")).toHaveCount(1);
  await expect(phone.locator(".map-card")).toHaveCount(0);
  await expect(desktop.locator(".maplibregl-canvas")).toHaveCount(1, { timeout: 20000 });
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(1);

  // A viewport change must destroy the hidden WebGL map rather than run both.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(desktop.locator(".map-card")).toHaveCount(0);
  await expect(phone.locator(".map-card")).toHaveCount(1);
  await phone.scrollIntoViewIfNeeded();
  await expect(phone.locator(".maplibregl-canvas")).toHaveCount(1, { timeout: 20000 });
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(1);

  // A collapsed mobile map releases its renderer; expanding creates just one.
  await page.getByRole("button", { name: /hide map/i }).click();
  await expect(phone.locator(".map-card")).toHaveCount(0);
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(0);
  await page.getByRole("button", { name: /show map/i }).click();
  await phone.scrollIntoViewIfNeeded();
  await expect(phone.locator(".maplibregl-canvas")).toHaveCount(1, { timeout: 20000 });
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(1);
});
