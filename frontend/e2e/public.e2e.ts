import { expect, test, type Page } from "@playwright/test";

// Console errors include Content-Security-Policy violations and failed requests: a page that
// renders but logs them is a regression.
function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test("the explore page draws the map without errors", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/");
  await expect(page).toHaveTitle(/Mediterranean Rescue/);
  await expect(page.locator(".maplibregl-canvas").filter({ visible: true }).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(errors).toEqual([]);
});

test("the about page reads in English and in French", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByRole("heading", { level: 1, name: "About the data" })).toBeVisible();
  await page.getByRole("button", { name: "Français" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "À propos des données" })).toBeVisible();
  // The choice is kept for the next visit.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "À propos des données" })).toBeVisible();
});

test("an application route loaded directly is served by the application", async ({ page }) => {
  const response = await page.goto("/workspace/history");
  expect(response?.status()).toBe(200);
  // Signed out: the team space asks to sign in, it never shows its data.
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("a used or forged invitation link explains itself", async ({ page }) => {
  await page.goto("/invite#not-a-real-token");
  await expect(page.getByRole("heading", { name: "This link no longer works" })).toBeVisible();
});

test("an operation opened from the feed has a link that reopens it", async ({ page }) => {
  await page.goto("/");
  const events = await page.request.get("/api/v1/events/?limit=1");
  const { items } = (await events.json()) as { items: { id: string }[] };
  test.skip(items.length === 0, "nothing is published on this instance");
  await page.goto(`/?event=${items[0]!.id}`);
  await expect(page.getByRole("link", { name: /Copy the link to this record|Copier le lien/ }).or(page.getByRole("button", { name: /Copy the link to this record|Copier le lien/ })).first()).toBeVisible();
});

test("the phone's first-visit notice leaves the map visible and expands its caveats", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const expand = page.getByRole("button", { name: "Read the three essential points" });
  await expect(expand).toBeVisible();
  await expect(expand).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#welcome-points")).toBeHidden();
  await expect(page.locator(".explore-map--inline")).toBeVisible();
  await expand.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#welcome-points")).toBeVisible();
  await expect(page.getByRole("button", { name: "Hide the essential points" })).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "Hide the essential points" }).click();
  await expect(page.locator("#welcome-points")).toBeHidden();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator("#welcome-points")).toBeVisible();
  await expect(page.getByRole("button", { name: "Read the three essential points" })).toBeHidden();
});
