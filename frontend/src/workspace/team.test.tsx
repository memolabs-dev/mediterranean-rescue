// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PublicationOverview } from "../api/client";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { PublishWorkspace } from "./PublishWorkspace";
import { TeamHome } from "./TeamHome";
import { journeyDone } from "./journey";

const PUBLISHER = {
  username: "volunteer",
  permissions: {
    review_identity: true,
    stage_snapshot: false,
    prepare_drafts: true,
    publish: true,
  },
};

function overview(overrides: Partial<PublicationOverview> = {}): PublicationOverview {
  return {
    sources: [{ key: "fixture", name: "Fictitious source", rights_approved: true }],
    preparation: [
      {
        sheet: "Data_operations",
        exported_at: "2026-10-24T12:00:00Z",
        ready: 2,
        prepared: 0,
        changed: 0,
        not_verified: 5,
        to_fix: 1,
      },
    ],
    events: { draft: 1, published: 0, withdrawn: 0 },
    can: { prepare: true, publish: true },
    ...overrides,
  };
}

const DRAFT = {
  id: "00000000-0000-0000-0000-0000000000f1",
  kind: "rescue",
  occurred_on: "2024-02-03",
  people: 42,
  port: "Port fictif",
  located: true,
  status: "draft",
  published_at: null,
  source: "Fictitious source",
  rights_approved: true,
};

function render(ui: ReactElement, path: string) {
  window.history.replaceState(null, "", path);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderWithI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function server(routes: Parameters<typeof fakeServer>[0] = {}) {
  return fakeServer({
    "GET /api/private/v1/me/": () => ({ body: PUBLISHER }),
    "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
    "GET /api/private/v1/publication/": () => ({ body: overview() }),
    ...routes,
  });
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("team home", () => {
  it("lists the work in order, says what is waiting and explains a locked step", async () => {
    server({
      "GET /api/private/v1/sync/": () => ({
        body: {
          sheets: [
            {
              sheet: "Data_operations",
              last_checked_at: "2026-10-24T12:00:00Z",
              last_status: "unchanged",
              last_message: "",
              last_change_at: null,
              last_change: {},
            },
          ],
        },
      }),
      "GET /api/private/v1/preview/events/": () => ({
        body: {
          items: [],
          total_count: 9,
          has_next: false,
          counts: { to_review: 7, blocked: 2, linked: 0 },
        },
      }),
      "GET /api/private/v1/ports/labels/": () => ({
        body: { items: [], total_count: 3, has_next: false },
      }),
      "GET /api/private/v1/publication/": () => ({
        body: overview({
          sources: [{ key: "fixture", name: "Fictitious source", rights_approved: false }],
        }),
      }),
    });
    render(<TeamHome />, "/workspace");
    expect(await screen.findByRole("heading", { name: "Hello volunteer" })).toBeTruthy();
    // One next task, with the only orange button; a newcomer practises first.
    const next = screen.getByRole("region", { name: "Your next task" });
    expect(within(next).getByRole("heading", { name: "Practise on an invented operation" })).toBeTruthy();
    expect(within(next).getByRole("link", { name: /Start/ }).getAttribute("href")).toBe("/workspace/practice");
    expect(screen.getByText("Discover the space")).toBeTruthy();
    const steps = within(screen.getByRole("region", { name: "All the work, in order" })).getAllByRole("listitem");
    expect(steps.map((step) => within(step).getByRole("heading").textContent)).toEqual([
      "Sheet reading",
      "Verify new or changed events",
      "Prepare verified events",
      "Publish",
    ]);
    expect(await within(steps[1]!).findByText(/7 events waiting to be verified\. 2 need a fix in the sheet \(found by the automatic checks\)\./)).toBeTruthy();
    expect(await within(steps[3]!).findByText("No written agreement recorded from: Fictitious source.")).toBeTruthy();
    expect(within(steps[3]!).getByText("Cannot start yet")).toBeTruthy();
    expect(await screen.findByText("3 port names to match to a known port.")).toBeTruthy();
    expect(journeyDone("intro", "volunteer")).toBe(true);
  });
});

describe("publish", () => {
  it("prepares verified events with a reason", async () => {
    const { calls } = server({
      "GET /api/private/v1/publication/events/": () => ({
        body: { items: [], total_count: 0, has_next: false },
      }),
      "POST /api/private/v1/publication/prepare/": () => ({
        body: {
          created: 2,
          overview: overview({
            events: { draft: 3, published: 0, withdrawn: 0 },
          }),
        },
      }),
    });
    render(<PublishWorkspace />, "/workspace/publish");
    const button = await screen.findByRole("button", {
      name: "Prepare 2 events",
    });
    expect(button.hasAttribute("disabled") || button.getAttribute("aria-disabled") === "true").toBe(true);
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "Checked against the logbook");
    await userEvent.click(screen.getByRole("button", { name: "Prepare 2 events" }));
    expect(await screen.findByText("2 events prepared. They stay private until they are published.")).toBeTruthy();
    expect(calls.find((call) => call.path === "/api/private/v1/publication/prepare/")?.body).toEqual({
      reason: "Checked against the logbook",
    });
  });

  it("publishes the ticked events after a confirmation that names the consequence", async () => {
    const { calls } = server({
      "GET /api/private/v1/publication/events/": () => ({
        body: { items: [DRAFT], total_count: 1, has_next: false },
      }),
      "POST /api/private/v1/publication/decisions/": () => ({
        body: { action: "publish", count: 1 },
      }),
    });
    render(<PublishWorkspace />, "/workspace/publish");
    await userEvent.click(await screen.findByRole("checkbox", { name: /Rescue operation/ }));
    await userEvent.type(screen.getAllByRole("textbox", { name: "Reason" }).at(-1)!, "Checked, rights confirmed");
    await userEvent.click(screen.getByRole("button", { name: "Publish 1 event" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/It will be visible to everyone on the public site/)).toBeTruthy();
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish 1 event" }));
    expect(await screen.findByText("1 event published. It is now on the public site.")).toBeTruthy();
    expect(calls.find((call) => call.path === "/api/private/v1/publication/decisions/")?.body).toEqual({
      action: "publish",
      events: [DRAFT.id],
      reason: "Checked, rights confirmed",
    });
  });

  it("explains a lock instead of offering to publish", async () => {
    server({
      "GET /api/private/v1/publication/": () => ({
        body: overview({
          sources: [{ key: "fixture", name: "Fictitious source", rights_approved: false }],
        }),
      }),
      "GET /api/private/v1/publication/events/": () => ({
        body: {
          items: [{ ...DRAFT, rights_approved: false }],
          total_count: 1,
          has_next: false,
        },
      }),
    });
    render(<PublishWorkspace />, "/workspace/publish");
    expect(
      await screen.findByRole("heading", {
        name: "Nothing can be published yet",
      }),
    ).toBeTruthy();
    await screen.findByText("Port fictif");
    await waitFor(() => expect(screen.queryByRole("checkbox")).toBeNull());
  });

  it("keeps the dialog open on a refusal and reloads the list behind it", async () => {
    const { calls } = server({
      "GET /api/private/v1/publication/events/": () => ({
        body: { items: [DRAFT], total_count: 1, has_next: false },
      }),
      "POST /api/private/v1/publication/decisions/": () => ({
        status: 409,
        body: { code: "conflict", detail: "x" },
      }),
    });
    render(<PublishWorkspace />, "/workspace/publish");
    await userEvent.click(await screen.findByRole("checkbox", { name: /Rescue operation/ }));
    await userEvent.type(screen.getAllByRole("textbox", { name: "Reason" }).at(-1)!, "Reviewed");
    await userEvent.click(screen.getByRole("button", { name: "Publish 1 event" }));
    const dialog = await screen.findByRole("alertdialog");
    const before = calls.filter((call) => call.path === "/api/private/v1/publication/events/").length;
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish 1 event" }));
    expect(await within(dialog).findByText(/Someone changed these events meanwhile/)).toBeTruthy();
    await waitFor(() => expect(calls.filter((call) => call.path === "/api/private/v1/publication/events/").length).toBeGreaterThan(before));
  });
});

describe("team home for a single role", () => {
  it("a publisher-only volunteer sees what is not their role instead of endless loading", async () => {
    const { calls } = server({
      "GET /api/private/v1/me/": () => ({
        body: {
          username: "publisher",
          permissions: {
            review_identity: false,
            stage_snapshot: false,
            prepare_drafts: false,
            publish: true,
          },
        },
      }),
    });
    render(<TeamHome />, "/workspace");
    const steps = within(await screen.findByRole("region", { name: "All the work, in order" })).getAllByRole("listitem");
    expect(within(steps[0]!).getByText("Not part of your role.")).toBeTruthy();
    expect(within(steps[1]!).getByText("Not part of your role.")).toBeTruthy();
    expect(within(steps[0]!).queryByRole("link")).toBeNull();
    expect(calls.some((call) => call.path === "/api/private/v1/sync/")).toBe(false);
    expect(screen.queryByRole("link", { name: /Manual update/ })).toBeNull();
  });
});
