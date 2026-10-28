import { expect, test, type Page } from "@playwright/test";

// Strictly disposable database, seeded with fictional CSV and randomly generated CI users.
// No auth traces/screenshots: even throwaway passwords must not leak into artifacts.
test.use({ trace: "off", video: "off" });

test.describe("authenticated fictional volunteer review", () => {
  test.skip(process.env.E2E_REVIEW_DEMO !== "1", "requires disposable training database");

  const password = process.env.RESCUE_REVIEW_DEMO_PASSWORD;
  const requirePassword = () => {
    expect(password?.length, "CI test password must exist").toBeGreaterThanOrEqual(24);
    return password!;
  };

  async function signIn(page: Page, username: string) {
    await page.goto("/workspace/review");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await page.getByRole("textbox", { name: "Username" }).fill(username);
    await page.getByLabel("Password").fill(requirePassword());
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
  }

  async function csrf(page: Page): Promise<string> {
    const r = await page.request.get("/api/csrf/");
    expect(r.ok()).toBe(true);
    const result = (await r.json()) as { csrfToken: string };
    return result.csrfToken;
  }

  test("browser review, recorded reason, publish and withdraw with distinct roles", async ({ page }, info) => {
    test.skip(info.project.name !== "chromium", "mutating CI journey runs exactly once");
    await expect((await page.request.get("/api/private/v1/me/")).status()).toBe(401);

    await signIn(page, "fictional-ci-reviewer");
    await expect(page.getByRole("heading", { name: "Verify events", exact: true }).first()).toBeVisible();

    const snapshotsResponse = await page.request.get("/api/private/v1/snapshots/?limit=100");
    expect(snapshotsResponse.ok()).toBe(true);
    const snapshots = (await snapshotsResponse.json()) as {
      items: { id: string; source: { key: string } }[];
    };
    const snapshot = snapshots.items.find((item) => item.source.key === "fictional-browser-review");
    expect(snapshot).toBeDefined();

    const queueResponse = await page.request.get(
      `/api/private/v1/review/rows/?snapshot=${snapshot!.id}&status=to_review`,
    );
    expect(queueResponse.ok()).toBe(true);
    const queue = (await queueResponse.json()) as { items: { id: string }[] };
    expect(queue.items).toHaveLength(1);
    const row = queue.items[0]!.id;

    await page.goto(`/workspace/review/${snapshot!.id}/rows/${row}`);
    await expect(page.getByRole("radio", { name: "A new event" })).toBeVisible();
    await page.getByRole("radio", { name: "A new event" }).click();
    const reviewReason = "FICTIONAL CSV: verified source date and operation category";
    await page.getByRole("textbox", { name: "Reason" }).fill(reviewReason);
    await page.getByRole("button", { name: "Save as a new event", exact: true }).click();

    await expect.poll(async () => {
      const result = await page.request.get(`/api/private/v1/review/rows/${row}/`);
      const body = (await result.json()) as { decision: { reason: string } | null };
      return body.decision?.reason ?? null;
    }).toBe(reviewReason);
    await page.goto("/workspace/history");
    await expect(page.getByText(reviewReason)).toBeVisible();
    // The reviewer cannot publish even when they can verify a record.
    const reviewerToken = await csrf(page);
    const forbidden = await page.request.post("/api/private/v1/publication/prepare/", {
      data: { reason: "Should be refused" },
      headers: { "X-CSRFToken": reviewerToken },
    });
    expect(forbidden.status()).toBe(403);

    await page.getByRole("button", { name: "Sign out" }).first().click();
    await expect.poll(async () => (await page.request.get("/api/private/v1/me/")).status()).toBe(401);

    await signIn(page, "fictional-ci-publisher");
    await expect(page.getByRole("heading", { name: "Verify events", exact: true })).toBeVisible();

    // Exercise the real private UI, not API shortcuts: preparing, publishing and withdrawing
    // must remain usable with the same authorization/CSRF rules as the backend.
    await page.goto("/workspace/publish");
    const preparation = page.locator('section[aria-labelledby="prepare-title"]');
    await expect(preparation.getByRole("button", { name: "Prepare 1 event" })).toBeVisible();
    await preparation.getByRole("textbox", { name: "Reason" }).fill("FICTIONAL prepared after human review");
    await preparation.getByRole("button", { name: "Prepare 1 event" }).click();
    await expect(preparation.getByText("1 event prepared. It stays private until it is published.")).toBeVisible();

    const draftsResponse = await page.request.get("/api/private/v1/publication/events/?status=draft&limit=100");
    expect(draftsResponse.ok()).toBe(true);
    const drafts = (await draftsResponse.json()) as { items: { id: string; source: string }[] };
    const draft = drafts.items.find((item) => item.source === "FICTIONAL review browser fixture");
    expect(draft).toBeDefined();

    const decision = page.locator('section[aria-labelledby="decide-title"]');
    await decision.getByRole("checkbox", { name: /Rescue operation/i }).check();
    await decision.getByRole("textbox", { name: "Reason" }).fill("FICTIONAL publication validated by test publisher");
    await decision.getByRole("button", { name: "Publish 1 event" }).click();
    const publishDialog = page.getByRole("alertdialog");
    await expect(publishDialog.getByText(/visible to everyone on the public site/)).toBeVisible();
    await publishDialog.getByRole("button", { name: "Publish 1 event" }).click();
    await expect(decision.getByText("1 event published. It is now on the public site.")).toBeVisible();
    await expect.poll(async () => (await page.request.get(`/api/v1/events/${draft!.id}/`)).status()).toBe(200);

    await page.goto(`/?event=${draft!.id}`);
    await expect(page.getByText("Fictitious training data")).toBeVisible();
    await page.goto("/workspace/history?scope=team");
    await expect(page.getByText("FICTIONAL publication validated by test publisher")).toBeVisible();

    await page.goto("/workspace/publish");
    const withdrawal = page.locator('section[aria-labelledby="decide-title"]');
    await withdrawal.getByRole("button", { name: /On the public site/ }).click();
    await withdrawal.getByRole("checkbox", { name: /Rescue operation/i }).check();
    await withdrawal.getByRole("textbox", { name: "Reason" }).fill("FICTIONAL withdrawal after browser proof");
    await withdrawal.getByRole("button", { name: "Withdraw 1 event" }).click();
    const withdrawDialog = page.getByRole("alertdialog");
    await expect(withdrawDialog.getByText(/disappear from the public site/)).toBeVisible();
    await withdrawDialog.getByRole("button", { name: "Withdraw 1 event" }).click();
    await expect(withdrawal.getByText("1 event withdrawn from the public site.")).toBeVisible();
    await expect.poll(async () => (await page.request.get(`/api/v1/events/${draft!.id}/`)).status()).toBe(404);
  });

  test("a signed-in outsider cannot review the fictional source", async ({ page }, info) => {
    test.skip(info.project.name === "chromium", "read-only boundary is checked on WebKit and phone");
    await signIn(page, "fictional-ci-outsider");
    await expect.poll(async () => (await page.request.get("/api/private/v1/review/rows/")).status()).toBe(403);
    await expect(page.getByText("You are signed in, but your account cannot open this section.")).toBeVisible();
  });
});
