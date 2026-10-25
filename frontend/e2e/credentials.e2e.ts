import { expect, test } from "@playwright/test";

// Synthetic, intercepted API: no volunteer record or credential touches the live server.
test("invited volunteer saves sign-in credentials from the dashboard", async ({ page }) => {
  const posts: unknown[] = [];
  let saved = false;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    let response: unknown;
    let status = 200;
    if (path === "/api/csrf/") response = { csrfToken: "synthetic-csrf" };
    else if (path === "/api/private/v1/me/") {
      response = { username: "fictitious-volunteer", decisions: 0, permissions: {
        review_identity: true, stage_snapshot: false, prepare_drafts: false, publish: false, invite: false,
      } };
    } else if (path === "/api/private/v1/credentials/" && req.method() === "GET") {
      response = { needs_setup: !saved };
    } else if (path === "/api/private/v1/credentials/" && req.method() === "POST") {
      posts.push(req.postDataJSON());
      saved = true;
      response = { needs_setup: false };
    } else {
      response = { code: "not_found", detail: "Synthetic route" };
      status = 404;
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(response) });
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Keep your volunteer access" })).toBeVisible();
  await page.getByRole("button", { name: "Secure my access" }).click();
  expect(posts).toHaveLength(0);
  await page.getByRole("textbox", { name: "New password" }).fill("SyntheticLong#Credential2026");
  await page.getByRole("textbox", { name: "Repeat password" }).fill("SyntheticLong#Credential2026");
  await page.getByRole("button", { name: "Secure my access" }).click();
  await expect(page.getByRole("status")).toContainText("Your password is saved");
  expect(posts).toEqual([{ password: "SyntheticLong#Credential2026", confirmation: "SyntheticLong#Credential2026" }]);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Keep your volunteer access" })).toBeHidden();
  expect(errors).toEqual([]);
});
