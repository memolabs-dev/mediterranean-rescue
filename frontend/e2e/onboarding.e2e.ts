import { expect, test } from "@playwright/test";

// Isolated browser journey with synthetic data. No test writes to the live association data;
// only JS/CSS/assets are loaded from the running production image.
const SNAPSHOT = "00000000-0000-0000-0000-00000000000a";
const ROW = "00000000-0000-0000-0000-0000000000b1";
const IDENTITY = "00000000-0000-0000-0000-0000000000c1";
const TOKEN = "fictitious-onboarding-invite-token";

const permissions = {
  review_identity: true,
  stage_snapshot: false,
  prepare_drafts: false,
  publish: false,
  invite: false,
};

test("an invited volunteer practises and opens the first review without inheriting another account's progress", async ({ page }) => {
  let username = "fictitious-volunteer-one";
  const observedWrites: string[] = [];

  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (method === "POST") observedWrites.push(path);

    const me = { username, decisions: 0, permissions };
    const body =
      path === "/api/csrf/" ? { csrfToken: "synthetic-csrf" } :
      path === "/api/private/v1/invitations/check/" ? { invited_by: "fictitious-coordinator", roles: ["verify"], expires_at: "2026-10-28T10:00:00Z" } :
      path === "/api/private/v1/invitations/accept/" ? me :
      path === "/api/private/v1/me/" ? me :
      path === "/api/private/v1/sync/" ? { sheets: [] } :
      path === "/api/private/v1/logbook/" ? { rows: 0 } :
      path === "/api/private/v1/preview/events/" ? { items: [], total_count: 1, has_next: false, counts: { to_review: 1, blocked: 0, linked: 0 } } :
      path === "/api/private/v1/publication/" ? { sources: [], preparation: [], events: { draft: 0, published: 0, withdrawn: 0 }, can: { prepare: false, publish: false } } :
      path === "/api/private/v1/ports/labels/" ? { items: [], total_count: 0, has_next: false } :
      path === "/api/private/v1/snapshots/" ? {
        items: [{
          id: SNAPSHOT,
          source: { key: "fixture", name: "Fictitious source" },
          sheet: "Data_operations",
          created_at: "2026-10-24T12:00:00Z",
          row_count: 1,
          source_read: "end_unverified",
          contract_version: "v1",
        }],
        total_count: 1,
        has_next: false,
      } :
      path === "/api/private/v1/review/rows/" ? {
        items: [{
          id: ROW, line: 12, status: "to_review", proposal: "candidates",
          candidate_count: 1, repeats_line: null, occurred_on: "2024-02-03",
          kind: "rescue", people: 42, deaths: null, error_codes: [],
        }],
        total_count: 1, has_next: false, counts: { to_review: 1, blocked: 0, linked: 0 },
      } :
      path === `/api/private/v1/review/rows/${ROW}/` ? {
        id: ROW, line: 12, row_ref: "Data_operations@sha256:fixture#L12",
        snapshot: { id: SNAPSHOT, sheet: "Data_operations", sha256: "fixture", contract_version: "sheets-observed-v1" },
        status: "to_review",
        received: { headers: ["date", "nb_survivor"], cells: ["03/02/2024", "42"] },
        interpreted: { occurred_on: "2024-02-03", kind: "rescue", nb_survivor: 42, position: null },
        error_codes: [],
        proposal: {
          kind: "candidates",
          candidates: [{ id: IDENTITY, external_id: `Data_operations:${IDENTITY}`, summary: { occurred_on: "2024-02-03", kind: "rescue", people: 40, deaths: null } }],
          repeats_line: null,
        },
        decision: null,
        evidence: null,
      } : null;

    await route.fulfill({
      status: body === null ? 404 : 200,
      contentType: "application/json",
      body: JSON.stringify(body ?? { code: "not_found", detail: "Synthetic route not available" }),
    });
  });

  await page.goto(`/invite#${TOKEN}`);
  await expect(page.getByRole("heading", { name: "Welcome to the team" })).toBeVisible();
  await page.getByRole("button", { name: "Join the team" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  const next = page.getByRole("region", { name: "Your next task" });
  await expect(next.getByRole("heading", { name: "Practise on an invented operation" })).toBeVisible();
  await next.getByRole("link", { name: "Start" }).click();
  await expect(page.getByRole("heading", { name: "Practise on an invented operation" })).toBeVisible();

  // The real buttons must work with a keyboard on desktop and emulated phone.
  const answer = page.getByRole("button", { name: "No, something is wrong" });
  await answer.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Decide later/ })).toBeVisible();
  await page.getByRole("button", { name: /Decide later/ }).click();
  await page.getByRole("link", { name: /Back to the dashboard/ }).click();
  await expect(next.getByRole("heading", { name: "Verify an operation" })).toBeVisible();
  await next.getByRole("link", { name: "Start" }).click();
  const queue = page.getByRole("table", { name: "Events: To verify" });
  await expect(queue).toBeVisible();
  await queue.getByRole("link", { name: /Feb 3, 2024.*Rescue operation/ }).click();
  await expect(page.getByRole("table", { name: "As written in the sheet" })).toBeVisible();
  // Revalidation can repeat the read-only POST /check/ after joining. It must
  // never create an event decision or a publication during onboarding.
  expect(observedWrites.filter((path) => path.endsWith("/invitations/accept/"))).toHaveLength(1);
  expect(observedWrites.every((path) => [
    "/api/private/v1/invitations/check/",
    "/api/private/v1/invitations/accept/",
  ].includes(path))).toBe(true);

  // Account switch in the same browser must not inherit the first person's finished practice.
  username = "fictitious-volunteer-two";
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Hello fictitious-volunteer-two" })).toBeVisible();
  await expect(next.getByRole("heading", { name: "Practise on an invented operation" })).toBeVisible();
});