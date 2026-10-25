import { expect, test } from "@playwright/test";

// Every API response is invented and intercepted. The production instance receives no writes.
test("coordinator prepares a fresh link without silently restoring permissions", async ({ page }) => {
  const posts: unknown[] = [];
  const volunteer = "returning@example.org";
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    let body: unknown;
    let status = 200;
    if (path === "/api/csrf/") body = { csrfToken: "synthetic-token" };
    else if (path === "/api/private/v1/me/") {
      body = {
        username: "fictitious-coordinator",
        decisions: 0,
        permissions: {
          review_identity: false,
          stage_snapshot: false,
          prepare_drafts: false,
          publish: false,
          invite: true,
        },
      };
    } else if (path === "/api/private/v1/invitations/" && method === "GET") {
      body = {
        roles: [{ id: 1, key: "verify" }, { id: 2, key: "prepare" }],
        items: [{
          id: "00000000-0000-0000-0000-0000000000e2",
          email: volunteer,
          roles: ["prepare"],
          invited_by: "fictitious-coordinator",
          created_at: "2026-10-22T10:00:00Z",
          expires_at: "2026-10-25T10:00:00Z",
          status: "used",
          used_by: "fictitious-returning-volunteer",
        }],
      };
    } else if (path === "/api/private/v1/invitations/" && method === "POST") {
      posts.push(route.request().postDataJSON());
      body = {
        id: "00000000-0000-0000-0000-0000000000e3",
        token: "synthetic-new-single-use-token",
        expires_at: "2026-10-28T10:00:00Z",
      };
      status = 201;
    } else {
      status = 404;
      body = { code: "not_found", detail: "Synthetic route unavailable" };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/workspace/team");
  const again = page.getByRole("button", { name: "Prepare a new link" });
  await expect(again).toBeVisible();
  await again.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("textbox", { name: "Their email address" })).toHaveValue(volunteer);
  await expect(page.getByText(/no permissions are copied automatically/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Prepare verified events" })).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("checkbox", { name: "Verify events and port names" })).toHaveAttribute("aria-checked", "false");
  expect(posts).toEqual([]);

  await page.getByRole("button", { name: "Create the invitation link" }).click();
  await expect(page.getByRole("alert")).toContainText("Choose at least one volunteer role.");
  expect(posts).toEqual([]);
  await page.getByRole("checkbox", { name: "Verify events and port names" }).click();
  await page.getByRole("button", { name: "Create the invitation link" }).click();
  await expect(page.getByText(/synthetic-new-single-use-token/)).toBeVisible();
  expect(posts).toEqual([{ email: volunteer, roles: [1] }]);
});
