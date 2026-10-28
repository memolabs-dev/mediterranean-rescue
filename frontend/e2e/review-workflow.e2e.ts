import { expect, test, type Page } from "@playwright/test";

const REVIEWER = "__fictional_review_browser__";
const PUBLISHER = "__fictional_publish_browser__";
const SOURCE = "fictional-review-browser";

async function signIn(page: Page, username: string) {
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(process.env.E2E_REVIEW_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect.poll(async () => {
    const me = await page.request.get("/api/private/v1/me/");
    return me.ok() ? ((await me.json()) as { username: string }).username : null;
  }).toBe(username);
  await expect(page.getByText(username).filter({ visible: true }).first()).toBeVisible();
}

test.describe("authenticated fictional review proof", () => {
  test.skip(
    process.env.E2E_KICKOFF !== "1" || !process.env.E2E_REVIEW_PASSWORD,
    "requires disposable training login fixture and CI-generated password",
  );

  // The one state-changing workflow is intentionally serialized on Chromium.
  // Other browsers perform read-only permission checks, never a concurrent review.
  test("reviewer and publisher are different people; review, publish and withdraw", async ({ page }, info) => {
    test.skip(info.project.name !== "chromium", "state-changing proof runs once on Chromium");

    await page.goto("/workspace/review");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    const anonymous = await page.request.get("/api/private/v1/review/rows/");
    expect(anonymous.status()).toBe(401);

    await signIn(page, REVIEWER);
    const snapshots = await page.request.get("/api/private/v1/snapshots/");
    expect(snapshots.ok()).toBe(true);
    const snapshotItems = (await snapshots.json()) as {
      items: { id: string; source: { key: string } }[];
    };
    const snapshot = snapshotItems.items.find((item) => item.source.key === SOURCE);
    expect(snapshot).toBeDefined();
    const queue = await page.request.get(`/api/private/v1/review/rows/?snapshot=${snapshot!.id}`);
    const queueRows = (await queue.json()) as { items: { id: string }[] };
    expect(queueRows.items).toHaveLength(1);
    const row = queueRows.items[0]!;

    // A role with review permission has no authority to publish.
    const unauthorized = await page.request.post("/api/private/v1/publication/decisions/", {
      data: { action: "publish", events: [row.id], reason: "Not a publisher" },
    });
    expect(unauthorized.status()).toBe(403);

    await page.goto(`/workspace/review/${snapshot!.id}/rows/${row.id}`);
    await expect(page.getByRole("heading", { name: "Verify events" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "A new event" })).toBeVisible();
    await page.getByRole("radio", { name: "A new event" }).check();
    await page.getByRole("textbox", { name: "Reason" }).fill("Fictional source row checked against invented exercise");
    await page.getByRole("button", { name: "Save as a new event", exact: true }).click();
    await expect(page.getByText(/Saved. This event is verified/)).toBeVisible();
    const reviewed = await page.request.get(`/api/private/v1/review/rows/${row.id}/`);
    expect((await reviewed.json()).decision.reason).toContain("Fictional source row");

    await page.goto("/workspace/history");
    await expect(page.getByText("Fictional source row checked against invented exercise")).toBeVisible();
    await page.screenshot({ path: info.outputPath("fictional-volunteer-review.png") });

    await page.getByRole("button", { name: "Sign out" }).first().click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await signIn(page, PUBLISHER);
    expect((await page.request.get(`/api/private/v1/review/rows/?snapshot=${snapshot!.id}`)).status()).toBe(403);

    await page.goto("/workspace/publish");
    const prepare = page.locator('section[aria-labelledby="prepare-title"]');
    await prepare.getByRole("textbox", { name: "Reason" }).fill("Prepared only from invented exercise");
    await prepare.locator('button[type="submit"]').click();
    const drafts = await page.request.get("/api/private/v1/publication/events/?status=draft");
    const draftItems = (await drafts.json()) as { items: { id: string; source: string }[] };
    const event = draftItems.items.find((item) => item.source === "SYNTHETIC browser review source");
    expect(event).toBeDefined();

    const decision = page.locator('section[aria-labelledby="decide-title"]');
    await decision.getByRole("checkbox", { name: /Rescue.*17.*2026/ }).check();
    await decision.getByRole("textbox", { name: "Reason" }).fill("Approved invented training publication");
    await decision.getByRole("button", { name: /Publish/ }).last().click();
    await page.getByRole("dialog").getByRole("button", { name: /Publish/ }).click();
    await expect.poll(async () => {
      const r = await page.request.get(`/api/v1/events/${event!.id}/`);
      return r.status();
    }).toBe(200);
    await page.screenshot({ path: info.outputPath("fictional-volunteer-published.png") });

    await decision.getByRole("button", { name: /Published/ }).click();
    await decision.getByRole("checkbox", { name: /Rescue.*17.*2026/ }).check();
    await decision.getByRole("textbox", { name: "Reason" }).fill("Withdrawing invented training publication");
    await decision.getByRole("button", { name: /Withdraw/ }).last().click();
    await page.getByRole("dialog").getByRole("button", { name: /Withdraw/ }).click();
    await expect.poll(async () => {
      const r = await page.request.get(`/api/v1/events/${event!.id}/`);
      return r.status();
    }).toBe(404);
    await page.goto("/workspace/history");
    await expect(page.getByText("Withdrawing invented training publication")).toBeVisible();
    await page.screenshot({ path: info.outputPath("fictional-volunteer-withdrawn.png") });
  });

  test("a signed-in publisher cannot open volunteer review", async ({ page }, info) => {
    test.skip(info.project.name === "chromium", "Chromium covers the state-changing proof");
    await signIn(page, PUBLISHER);
    await page.goto("/workspace/review");
    await expect(page.getByText("You are signed in, but your account cannot open this section.")).toBeVisible();
  });
});
