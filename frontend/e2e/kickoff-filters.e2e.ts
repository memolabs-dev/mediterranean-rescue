import { expect, test } from "@playwright/test";

test.describe("fictional filter quality", () => {
  test.skip(process.env.E2E_KICKOFF !== "1", "requires the isolated fictional training stack");

  test("kind, date and reset filters update the feed without leaving a stale record open", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator("li.card:not(.card--skeleton)");
    await expect(cards).toHaveCount(2);

    // An opened record should not be left attached to a different filter context.
    await cards.first().getByRole("button").first().click();
    await expect(page.locator("li.card.card--open")).toHaveCount(1);
    await page.locator(".chips").getByRole("button", { name: "Transfers" }).click();
    await expect(cards).toHaveCount(0);
    await expect(page.locator("li.card.card--open")).toHaveCount(0);
    await page.locator(".chips").getByRole("button", { name: "All events" }).click();
    await expect(cards).toHaveCount(2);

    await page.locator(".chip--period").click();
    await page.locator('.composer__period input[type="date"]').first().fill("2027-01-01");
    await expect(cards).toHaveCount(0);
    await page.locator(".explore-meta__actions").getByRole("button", { name: "Reset filters" }).click();
    await expect(cards).toHaveCount(2);
    await expect(page.locator('.composer__period input[type="date"]').first()).toHaveValue("");
  });
});
