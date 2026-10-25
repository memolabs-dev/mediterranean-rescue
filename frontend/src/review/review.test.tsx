// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { QueueItem, RowDetail } from "../api/client";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { ReviewWorkspace } from "./ReviewWorkspace";

const SNAPSHOT = "00000000-0000-0000-0000-00000000000a";
const ROW = "00000000-0000-0000-0000-0000000000b1";
const IDENTITY = "00000000-0000-0000-0000-0000000000c1";

function rowDetail(overrides: Partial<RowDetail> = {}): RowDetail {
  return {
    id: ROW,
    line: 12,
    row_ref: `Data_operations@sha256:abc#L12`,
    snapshot: { id: SNAPSHOT, sheet: "Data_operations", sha256: "abc", contract_version: "sheets-observed-v1" },
    status: "to_review",
    received: { headers: ["date", "nb_survivor", ""], cells: ["03/02/2024", "42", "<b>raw</b>"] },
    interpreted: { occurred_on: "2024-02-03", kind: "rescue", nb_survivor: 42, position: null },
    error_codes: [],
    proposal: {
      kind: "candidates",
      candidates: [{ id: IDENTITY, external_id: `Data_operations:${IDENTITY}`, summary: { occurred_on: "2024-02-03", kind: "rescue", people: 40, deaths: null } }],
      repeats_line: null,
    },
    decision: null,
    evidence: null,
    ...overrides,
  };
}

function queueItem(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    id: ROW,
    line: 12,
    status: "to_review",
    proposal: "candidates",
    candidate_count: 1,
    repeats_line: null,
    occurred_on: "2024-02-03",
    kind: "rescue",
    people: 42,
    deaths: null,
    error_codes: [],
    ...overrides,
  };
}

const ME = { username: "reviewer", permissions: { review_identity: true } };
const SNAPSHOTS = {
  items: [{ id: SNAPSHOT, source: { key: "s", name: "S" }, sheet: "Data_operations", created_at: "2026-10-24T12:00:00Z", row_count: 2, source_read: "end_unverified", contract_version: "v1" }],
  total_count: 1,
  has_next: false,
};

function renderAt(path: string) {
  window.history.replaceState(null, "", path);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(
    <QueryClientProvider client={client}>
      <ReviewWorkspace />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});
afterEach(() => vi.unstubAllGlobals());

describe("access", () => {
  it("asks to sign in on 401 with the application's own form, then loads the workspace", async () => {
    let signedIn = false;
    const { calls } = fakeServer({
      "GET /api/private/v1/me/": () =>
        signedIn ? { body: ME } : { status: 401, body: { code: "not_authenticated", detail: "x" } },
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "POST /api/private/v1/session/": (call) => {
        const body = call.body as { username: string; password: string };
        if (body.password !== "right") return { status: 400, body: { code: "invalid_credentials", detail: "x" } };
        signedIn = true;
        return { body: ME };
      },
      "GET /api/private/v1/snapshots/": () => ({ body: SNAPSHOTS }),
      "GET /api/private/v1/review/rows/": () => ({ body: { items: [], total_count: 0, has_next: false, counts: { to_review: 0, blocked: 0, linked: 0 } } }),
    });
    renderAt("/workspace/review");
    await screen.findByRole("heading", { name: "Sign in" });
    expect(screen.getByText(/returning without a password.*new invitation link/i)).toBeTruthy();
    await userEvent.type(screen.getByRole("textbox", { name: "Username" }), "reviewer");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Username or password is incorrect.")).toBeTruthy();
    await userEvent.clear(screen.getByLabelText("Password"));
    await userEvent.type(screen.getByLabelText("Password"), "right");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect((await screen.findAllByTitle("Signed in as reviewer")).length).toBeGreaterThan(0);
    const signIn = calls.filter((call) => call.method === "POST" && call.path === "/api/private/v1/session/").at(-1);
    expect(signIn?.headers.get("X-CSRFToken")).toBe("t");
  });

  it("says the permission is missing instead of showing an empty queue", async () => {
    fakeServer({ "GET /api/private/v1/me/": () => ({ body: { username: "x", permissions: { review_identity: false } } }) });
    renderAt("/workspace/review");
    expect(await screen.findByText(/your account cannot open this section/)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("queue (W04)", () => {
  it("shows counts per facet, rows with a title link, and carries only unchanged rows", async () => {
    const carry = { id: "00000000-0000-0000-0000-0000000000b2", line: 13, occurred_on: "2024-01-19", proposal: "exact_carry" as const, candidate_count: 1 };
    const { calls } = fakeServer({
      "GET /api/private/v1/me/": () => ({ body: ME }),
      "GET /api/private/v1/snapshots/": () => ({ body: SNAPSHOTS }),
      "GET /api/private/v1/review/rows/": () => ({
        body: { items: [queueItem(), queueItem(carry)], total_count: 2, has_next: false, counts: { to_review: 2, blocked: 1, linked: 5 } },
      }),
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "POST /api/private/v1/review/snapshots/:id/exact-carries/": () => ({ body: { carried: 1 } }),
    });
    renderAt("/workspace/review");
    const table = await screen.findByRole("table", { name: "Events: To verify" });
    expect(screen.getByRole("radio", { name: "Verified 5" })).toBeTruthy();
    expect(within(table).getByRole("link", { name: "Feb 3, 2024 · Rescue operation" }).getAttribute("href")).toBe(
      `/workspace/review/${SNAPSHOT}/rows/${ROW}?status=to_review&offset=0`,
    );
    expect(within(table).queryByRole("checkbox", { name: "Select the event of Feb 3, 2024 · Rescue operation" })).toBeNull();
    await userEvent.click(within(table).getByRole("checkbox", { name: "Select the event of Jan 19, 2024 · Rescue operation" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm 1 unchanged event" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Reason" }), "Same content as before");
    await userEvent.click(within(dialog).getByRole("button", { name: "Confirm 1 event" }));
    expect(await screen.findByText("1 event verified.")).toBeTruthy();
    const post = calls.find((call) => call.method === "POST");
    expect(post?.body).toEqual({ rows: [carry.id], reason: "Same content as before" });
    expect(post?.headers.get("X-CSRFToken")).toBe("t");
  });

  it("changes facet through the URL and resets the page", async () => {
    const { calls } = fakeServer({
      "GET /api/private/v1/me/": () => ({ body: ME }),
      "GET /api/private/v1/snapshots/": () => ({ body: SNAPSHOTS }),
      "GET /api/private/v1/review/rows/": () => ({ body: { items: [], total_count: 0, has_next: false, counts: { to_review: 0, blocked: 1, linked: 0 } } }),
    });
    renderAt("/workspace/review?offset=25");
    expect(await screen.findByText("Every event is verified")).toBeTruthy();
    await userEvent.click(screen.getByRole("radio", { name: "To fix in the sheet 1" }));
    await waitFor(() => expect(window.location.search).toBe(`?snapshot=${SNAPSHOT}&status=blocked&offset=0`));
    await waitFor(() => expect(calls.at(-1)?.query.get("status")).toBe("blocked"));
  });
});

describe("row review (W05)", () => {
  function server(decision: (body: unknown) => { status?: number; body: unknown }) {
    let current = rowDetail();
    return fakeServer({
      "GET /api/private/v1/me/": () => ({ body: ME }),
      "GET /api/private/v1/snapshots/": () => ({ body: SNAPSHOTS }),
      "GET /api/private/v1/review/rows/": () => ({ body: { items: [queueItem()], total_count: 1, has_next: false, counts: { to_review: 1, blocked: 0, linked: 0 } } }),
      "GET /api/private/v1/review/rows/:id/": () => ({ body: current }),
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "POST /api/private/v1/review/rows/:id/decision/": (call) => {
        const result = decision(call.body);
        if (!result.status || result.status === 200) current = result.body as RowDetail;
        return result;
      },
    });
  }

  it("shows received values as text, the interpretation and the candidates, choosing none", async () => {
    server(() => ({ body: rowDetail() }));
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    const received = await screen.findByRole("table", { name: "As written in the sheet" });
    expect(within(received).getByText("<b>raw</b>")).toBeTruthy();
    expect(within(received).getByText("Column 3 (no header)")).toBeTruthy();
    expect(screen.getByText("Events already verified share this date and type. Say whether it is one of them; nothing is chosen for you.")).toBeTruthy();
    await userEvent.click(screen.getByRole("radio", { name: "The same event as one already verified" }));
    const candidate = screen.getByRole("radio", { name: /Rescue operation · Feb 3, 2024 · 40 people reported/ });
    expect(candidate.getAttribute("aria-checked")).toBe("false");
  });

  it("summarizes missing answers, then creates the identity with the CSRF token", async () => {
    const { calls } = server((body) => ({
      body: rowDetail({
        status: "linked",
        proposal: { kind: "linked", candidates: [], repeats_line: null },
        decision: { identity: IDENTITY, external_id: `Data_operations:${IDENTITY}`, match: "new", approved_by: "reviewer", approved_at: "2026-10-24T12:00:00Z", reason: (body as { reason: string }).reason },
      }),
    }));
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("button", { name: "Save as a new event" }));
    expect(await screen.findByRole("heading", { name: "There are 2 problems" })).toBeTruthy();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await userEvent.click(screen.getByRole("radio", { name: "A new event" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "First observation");
    await userEvent.click(screen.getByRole("button", { name: "Save as a new event" }));
    expect(await screen.findByText("Saved. This event is verified (private, not published).")).toBeTruthy();
    const post = calls.find((call) => call.method === "POST");
    expect(post?.body).toEqual({ action: "create_identity", reason: "First observation" });
    expect(post?.headers.get("X-CSRFToken")).toBe("t");
    expect(screen.getByText("First observation")).toBeTruthy();
  });

  it("explains a conflict and reads the state again", async () => {
    const { calls } = server(() => ({ status: 409, body: { code: "conflict", detail: "This row is already linked" } }));
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "The same event as one already verified" }));
    await userEvent.click(screen.getByRole("radio", { name: /Rescue operation · Feb 3, 2024/ }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "Same rescue");
    await userEvent.click(screen.getByRole("button", { name: "Confirm it is the same event" }));
    expect(await screen.findByText(/Someone else changed this event/)).toBeTruthy();
    const post = calls.find((call) => call.method === "POST");
    expect(post?.body).toEqual({ action: "link", identity: IDENTITY, reason: "Same rescue" });
    await waitFor(() => expect(calls.filter((call) => call.path === `/api/private/v1/review/rows/${ROW}/`).length).toBe(2));
  });

  it("review later saves nothing", async () => {
    const { calls } = server(() => ({ body: rowDetail() }));
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "Decide later" }));
    await userEvent.click(screen.getByRole("button", { name: "Close without saving" }));
    await waitFor(() => expect(window.location.pathname).toBe("/workspace/review"));
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });
});


describe("review regressions", () => {
  function server(extra: Parameters<typeof fakeServer>[0] = {}) {
    return fakeServer({
      "GET /api/private/v1/me/": () => ({ body: ME }),
      "GET /api/private/v1/snapshots/": () => ({ body: SNAPSHOTS }),
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "GET /api/private/v1/review/rows/": () => ({
        body: {
          items: [queueItem(), queueItem({ id: "00000000-0000-0000-0000-0000000000b2", line: 13 })],
          total_count: 2,
          has_next: false,
          counts: { to_review: 2, blocked: 0, linked: 0 },
        },
      }),
      "GET /api/private/v1/review/rows/:id/": () => ({ body: rowDetail() }),
      "GET /api/private/v1/review/identities/": () => ({ body: { items: [] } }),
      ...extra,
    });
  }

  it("pressing Enter in the identity search never records a decision", async () => {
    const { calls } = server();
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "The same event as one already verified" }));
    await userEvent.click(screen.getByRole("radio", { name: /Rescue operation · Feb 3, 2024/ }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "Same rescue{Enter}");
    await userEvent.type(screen.getByRole("combobox", { name: "Or find another verified event" }), "2024-02{Enter}");
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("'and next' opens the row after the current one once the server confirmed", async () => {
    server({
      "POST /api/private/v1/review/rows/:id/decision/": () => ({
        body: rowDetail({ status: "linked", proposal: { kind: "linked", candidates: [], repeats_line: null } }),
      }),
    });
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "A new event" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "New");
    await userEvent.click(screen.getByRole("button", { name: "Save as a new event, then the next one" }));
    await waitFor(() =>
      expect(window.location.pathname).toBe(`/workspace/review/${SNAPSHOT}/rows/00000000-0000-0000-0000-0000000000b2`),
    );
  });

  it("a row entered twice in the sheet says where the first one is and offers no decision", async () => {
    server({
      "GET /api/private/v1/review/rows/:id/": () => ({
        body: rowDetail({ status: "blocked", proposal: { kind: "repeat", candidates: [], repeats_line: 2 } }),
      }),
    });
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    expect(await screen.findByText(/This row copies row 2 of the same sheet, cell for cell\./)).toBeTruthy();
    expect(screen.queryByRole("radio", { name: "A new event" })).toBeNull();
  });

  it("asks before leaving a row with a typed reason", async () => {
    server();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "A new event" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "Half typed");
    await userEvent.click(screen.getAllByRole("link", { name: "Feb 3, 2024 · Rescue operation" })[1]!);
    expect(confirm).toHaveBeenCalledOnce();
    expect(window.location.pathname).toBe(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    confirm.mockRestore();
  });

  it("an expired session during a write shows the sign-in screen", async () => {
    let expired = false;
    server({
      "GET /api/private/v1/me/": () =>
        expired ? { status: 401, body: { code: "not_authenticated", detail: "x" } } : { body: ME },
      "POST /api/private/v1/review/rows/:id/decision/": () => {
        expired = true;
        return { status: 401, body: { code: "not_authenticated", detail: "x" } };
      },
    });
    renderAt(`/workspace/review/${SNAPSHOT}/rows/${ROW}`);
    await screen.findByRole("table", { name: "As written in the sheet" });
    await userEvent.click(screen.getByRole("radio", { name: "A new event" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Reason" }), "New");
    await userEvent.click(screen.getByRole("button", { name: "Save as a new event" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  });

  it("a malformed address does not crash the workspace", async () => {
    server();
    renderAt("/workspace/review/%E0/rows/x");
    expect(await screen.findByRole("table", { name: "Events: To verify" })).toBeTruthy();
  });
});
