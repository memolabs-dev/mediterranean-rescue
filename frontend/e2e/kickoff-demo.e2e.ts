import { expect, test } from "@playwright/test";

// Run only on the ephemeral CI training stack or a deliberately isolated local database.
// The normal public-production E2E suite skips this file.
test.describe("fictional kickoff walkthrough", () => {
  test.skip(process.env.E2E_KICKOFF !== "1", "requires the fictional training-only stack");

  test("map, list, missing position, and training disclaimer", async ({ page }, testInfo) => {
    const response = await page.request.get("/api/v1/events/?limit=10");
    expect(response.ok()).toBe(true);
    const feed = (await response.json()) as {
      data_mode: string;
      total_count: number;
      items: { id: string; source: { synthetic: boolean }; people: number | null; position: object | null }[];
    };
    expect(feed.data_mode).toBe("training");
    expect(feed.total_count).toBe(2);
    expect(feed.items.every((item) => item.source.synthetic)).toBe(true);
    expect(feed.items.filter((item) => item.position !== null)).toHaveLength(1);
    expect(feed.items.filter((item) => item.people === null)).toHaveLength(1);

    const points = await page.request.get("/api/v1/map-points/");
    expect(points.ok()).toBe(true);
    const map = (await points.json()) as { located_count: number; points: object[] };
    expect(map.located_count).toBe(1);
    expect(map.points).toHaveLength(1);

    await page.goto("/");
    await expect(page.getByText("Training mode: every event and count shown is fictitious.")).toBeVisible();
    await expect(page.getByText(/These records and their example links are fictional test fixtures/)).toBeVisible();
    await expect(page.locator(".maplibregl-canvas").filter({ visible: true }).first()).toBeVisible();
    await expect(page.locator("li.card")).toHaveCount(2);
    // Let the map paint its loaded feature before preserving the visual evidence.
    await page.waitForTimeout(600);
    await page.screenshot({ path: testInfo.outputPath("kickoff-fictional-map.png"), fullPage: true });
  });

  test("fictional event has a precise evidence link and French disclaimer", async ({ page }, testInfo) => {
    const response = await page.request.get("/api/v1/events/?limit=10");
    expect(response.ok()).toBe(true);
    const feed = (await response.json()) as { items: { id: string; source_url: string }[] };
    const event = feed.items.find((item) => item.source_url === "https://example.org/fictional/rescue-001");
    expect(event).toBeDefined();

    await page.goto(`/?event=${event!.id}`);
    await expect(page.getByText("Fictitious training data")).toBeVisible();
    await expect(page.getByRole("link", { name: /Open the event source/ })).toHaveAttribute(
      "href",
      "https://example.org/fictional/rescue-001",
    );
    await page.locator(".card--open").first().screenshot({ path: testInfo.outputPath("kickoff-fictional-source-en.png") });
    await page.getByRole("button", { name: "Français" }).click();
    await expect(page.getByText("Données d’entraînement fictives")).toBeVisible();
    await page.locator(".card--open").first().screenshot({ path: testInfo.outputPath("kickoff-fictional-source-fr.png") });
  });

  test("workspace stays private without a volunteer session", async ({ page }) => {
    await page.goto("/workspace/history");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
});
