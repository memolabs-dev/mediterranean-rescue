// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { Explore } from "../explore/Explore";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";

// MapLibre needs WebGL; the map is replaced by its point count.
vi.mock("../components/Map", () => ({
  EventMap: ({ points }: { points: readonly unknown[] }) => <p>{`${points.length} map points`}</p>,
}));

const ROW = "00000000-0000-0000-0000-0000000000b1";
const SNAPSHOT = "00000000-0000-0000-0000-00000000000a";
const ITEM = {
  id: ROW,
  snapshot: SNAPSHOT,
  sheet: "Data_operations",
  line: 12,
  exported_at: "2026-10-24T12:00:00Z",
  source: { key: "fixture", name: "Fictitious source" },
  synthetic: true,
  status: "to_review",
  error_codes: [],
  occurred_on: "2024-02-03",
  kind: "rescue",
  people: 42,
  women: 10,
  minors: null,
  deaths: null,
  port_label: "Port fictif",
  boat_type: null,
  position: { longitude: 12.25, latitude: 34.5, inferred_hemisphere: false },
  image_count: 0,
};
const EMPTY_PUBLIC = {
  "GET /api/v1/events/": () => ({ body: { items: [], total_count: 0, has_next: false, data_mode: "production" } }),
  "GET /api/v1/map-points/": () => ({ body: { points: [], located_count: 0, truncated: false } }),
};

function renderApp(ui = <App />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => vi.unstubAllGlobals());

describe("main screen preview", () => {
  it("visitors see only published events and never call the preview", async () => {
    const { calls } = fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ status: 401, body: { code: "not_authenticated", detail: "x" } }),
    });
    renderApp();
    expect(await screen.findByText("Nothing published yet")).toBeTruthy();
    await screen.findByRole("link", { name: "Team sign-in" });
    expect(screen.queryByRole("group", { name: "Data shown" })).toBeNull();
    expect(calls.some((call) => call.path.startsWith("/api/private/v1/preview/"))).toBe(false);
  });

  it("the public page stays public even for a signed-in team member", async () => {
    const { calls } = fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/session/": () => ({ body: { signed_in: true, local_auto_login: false } }),
    });
    renderApp();
    expect(await screen.findByText("Nothing published yet")).toBeTruthy();
    expect(await screen.findByRole("link", { name: /Team space/ })).toBeTruthy();
    expect(screen.queryByText(/latest data received/)).toBeNull();
    expect(calls.some((call) => call.path.startsWith("/api/private/v1/preview/"))).toBe(false);
  });

  it("the team view shows the latest data, clearly marked private, and opens an event in place", async () => {
    fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ body: { username: "r", permissions: { review_identity: true, stage_snapshot: true } } }),
      "GET /api/private/v1/preview/events/": () => ({
        body: { items: [ITEM], total_count: 1, has_next: false, counts: { to_review: 1, blocked: 0, linked: 0 } },
      }),
      "GET /api/private/v1/preview/map-points/": () => ({
        body: { points: [{ id: ROW, longitude: 12.25, latitude: 34.5, kind: "rescue", status: "to_review" }], located_count: 1, truncated: false },
      }),
      "GET /api/private/v1/preview/events/:id/": () => ({ body: ITEM }),
    });
    renderApp(<Explore audience="team" />);
    expect(await screen.findByText(/latest data received/)).toBeTruthy();
    expect((await screen.findAllByText("1 map points")).length).toBeGreaterThan(0);
    const card = await screen.findByRole("button", { name: /Port fictif/ });
    expect(card.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(card);
    expect(card.getAttribute("aria-expanded")).toBe("true");
    const region = await screen.findByRole("region", { name: "Event record" });
    expect((await within(region).findByRole("link", { name: /Verify this event/ })).getAttribute("href")).toBe(
      `/workspace/review/${SNAPSHOT}/rows/${ROW}`,
    );
  });

  it("an opened record has its own address, which opens it again", async () => {
    const server = {
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ body: { username: "r", permissions: { review_identity: true, stage_snapshot: true } } }),
      "GET /api/private/v1/preview/events/": () => ({
        body: { items: [ITEM], total_count: 1, has_next: false, counts: { to_review: 1, blocked: 0, linked: 0 } },
      }),
      "GET /api/private/v1/preview/map-points/": () => ({ body: { points: [], located_count: 0, truncated: false } }),
      "GET /api/private/v1/preview/events/:id/": () => ({ body: ITEM }),
    };
    fakeServer(server);
    const first = renderApp(<Explore audience="team" />);
    await userEvent.click(await screen.findByRole("button", { name: /Port fictif/ }));
    expect(window.location.search).toBe(`?event=${ROW}`);
    expect(await screen.findByRole("button", { name: "Copy the link to this record" })).toBeTruthy();
    first.unmount();

    // Audit of 24 October 2026, D10: a record could not be linked to.
    renderApp(<Explore audience="team" />);
    const card = await screen.findByRole("button", { name: /Port fictif/ });
    expect(card.getAttribute("aria-expanded")).toBe("true");
  });

  it("the logbook chip filters, and Reset clears it", async () => {
    // Frontend audit of 25 October 2026: two address changes in one click undid each other.
    fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ body: { username: "r", permissions: { review_identity: true, stage_snapshot: true } } }),
      "GET /api/private/v1/preview/events/": () => ({
        body: { items: [], total_count: 0, has_next: false, counts: { to_review: 0, blocked: 0, linked: 0 } },
      }),
      "GET /api/private/v1/preview/map-points/": () => ({ body: { points: [], located_count: 0, truncated: false } }),
    });
    renderApp(<Explore audience="team" />);
    const chip = await screen.findByRole("button", { name: /Found in the logbook/ });
    await userEvent.click(chip);
    expect(window.location.search).toBe("?source=sos-logbook");
    await userEvent.click((await screen.findAllByRole("button", { name: "Reset filters" }))[0]!);
    expect(window.location.search).toBe("");
  });

  it("search words and kind chips reach the server", async () => {
    const { calls } = fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ status: 401, body: { code: "not_authenticated", detail: "x" } }),
    });
    renderApp();
    await screen.findByText("Nothing published yet");
    await userEvent.click(screen.getByRole("button", { name: "Shipwrecks" }));
    await userEvent.type(screen.getByRole("searchbox"), "lampedusa");
    await waitFor(() =>
      expect(
        calls.some((call) => call.path === "/api/v1/events/" && call.query.get("q") === "lampedusa" && call.query.get("kind") === "shipwreck"),
      ).toBe(true),
    );
    expect(await screen.findByText("Nothing matches")).toBeTruthy();
  });

  it("the view switcher offers three views and keeps the choice in the address", async () => {
    fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ status: 401, body: { code: "not_authenticated", detail: "x" } }),
      "GET /api/v1/timeline/": () => ({ body: { months: [] } }),
    });
    renderApp();
    const views = await screen.findByRole("group", { name: "View" });
    expect(within(views).getByRole("button", { name: /Feed/ }).getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(within(views).getByRole("button", { name: /Timeline/ }));
    expect(window.location.search).toBe("?view=timeline");
    expect((await screen.findAllByText("No event to place on the timeline yet.")).length).toBeGreaterThan(0);
  });

  it("the logbook groups events by month and opens one in place", async () => {
    window.history.replaceState(null, "", "/?view=logbook");
    fakeServer({
      ...EMPTY_PUBLIC,
      "GET /api/private/v1/me/": () => ({ body: { username: "r", permissions: { review_identity: true, stage_snapshot: true } } }),
      "GET /api/private/v1/preview/events/": () => ({
        body: {
          items: [ITEM, { ...ITEM, id: "00000000-0000-0000-0000-0000000000b2", occurred_on: "2024-01-19", people: null }],
          total_count: 2,
          has_next: false,
          counts: { to_review: 2, blocked: 0, linked: 0 },
        },
      }),
      "GET /api/private/v1/preview/map-points/": () => ({ body: { points: [], located_count: 0, truncated: false } }),
      "GET /api/private/v1/preview/events/:id/": () => ({ body: ITEM }),
    });
    renderApp(<Explore audience="team" />);
    expect(await screen.findByRole("heading", { name: /^February 2024\W+1 event · 42 people rescued$/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /January 2024.*1 event/ })).toBeTruthy();
    const entry = screen.getByRole("button", { name: /Rescue operation · 42 people rescued/ });
    await userEvent.click(entry);
    expect(entry.getAttribute("aria-expanded")).toBe("true");
    expect(await screen.findByRole("link", { name: /Verify this event/ })).toBeTruthy();
  });
});
