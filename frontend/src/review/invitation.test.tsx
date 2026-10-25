// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { TeamPeople } from "../workspace/TeamPeople";
import { InvitationPage } from "./InvitationPage";

const TOKEN = "fictitious-token-0123456789-abcdefghijklmnop";
const COORDINATOR = {
  username: "coordinator",
  permissions: { review_identity: false, stage_snapshot: false, prepare_drafts: false, publish: false, invite: true },
};

function render(ui: ReactElement, path: string) {
  window.history.replaceState(null, "", path);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => vi.unstubAllGlobals());

describe("invitation by link", () => {
  it("reads the invitation, then joins only on the button and leaves the token out of the address", async () => {
    const { calls } = fakeServer({
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "POST /api/private/v1/invitations/check/": () => ({
        body: { invited_by: "coordinator", roles: ["verify"], expires_at: "2026-10-28T10:00:00Z" },
      }),
      "POST /api/private/v1/invitations/accept/": () => ({ body: COORDINATOR }),
    });
    render(<InvitationPage />, `/invite#${TOKEN}`);
    expect(await screen.findByRole("heading", { name: "Welcome to the team" })).toBeTruthy();
    expect(screen.getByText("Verify events and port names")).toBeTruthy();
    // The token goes in the body, never in a URL.
    expect(calls.every((call) => !call.path.includes(TOKEN) && !call.query.toString().includes(TOKEN))).toBe(true);
    expect(calls.some((call) => call.path.endsWith("/accept/"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Join the team" }));
    await waitFor(() => expect(window.location.pathname).toBe("/workspace"));
    expect(calls.find((call) => call.path.endsWith("/accept/"))?.body).toEqual({ token: TOKEN });
  });

  it("a spent or made-up link says so and offers the sign-in page", async () => {
    fakeServer({
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "POST /api/private/v1/invitations/check/": () => ({ status: 409, body: { code: "invitation_unusable", detail: "x" } }),
    });
    render(<InvitationPage />, `/invite#${TOKEN}`);
    expect(await screen.findByRole("heading", { name: "This link no longer works" })).toBeTruthy();
  });

  it("refuses a roleless invitation in the form, then accepts an explicit role", async () => {
    const { calls } = fakeServer({
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "GET /api/private/v1/me/": () => ({ body: COORDINATOR }),
      "GET /api/private/v1/invitations/": () => ({
        body: { roles: [{ id: 1, key: "verify" }], items: [] },
      }),
      "POST /api/private/v1/invitations/": (call) => {
        expect(call.body).toEqual({ email: "new@example.org", roles: [1] });
        return { status: 201, body: { id: "00000000-0000-0000-0000-0000000000e1", token: TOKEN, expires_at: "2026-10-28T10:00:00Z" } };
      },
    });
    render(<TeamPeople />, "/workspace/team");
    await userEvent.type(await screen.findByRole("textbox", { name: "Their email address" }), "new@example.org");
    await userEvent.click(screen.getByRole("button", { name: "Create the invitation link" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).toBe("Choose at least one volunteer role.");
    expect(error.closest("fieldset")?.getAttribute("aria-invalid")).toBe("true");
    expect(calls.filter((call) => call.path === "/api/private/v1/invitations/" && call.method === "POST")).toHaveLength(0);
    await userEvent.click(screen.getByRole("checkbox", { name: "Verify events and port names" }));
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Create the invitation link" }));
    expect(await screen.findByRole("heading", { name: /new@example.org/ })).toBeTruthy();
    expect(calls.filter((call) => call.path === "/api/private/v1/invitations/" && call.method === "POST")).toHaveLength(1);
  });

  it("a coordinator creates a link with volunteer roles and sees it once", async () => {
    let created = false;
    fakeServer({
      "GET /api/csrf/": () => ({ body: { csrfToken: "t" } }),
      "GET /api/private/v1/me/": () => ({ body: COORDINATOR }),
      "GET /api/private/v1/invitations/": () => ({
        body: {
          roles: [{ id: 1, key: "verify" }, { id: 2, key: "prepare" }],
          items: created
            ? [{ id: "00000000-0000-0000-0000-0000000000e1", email: "new@example.org", roles: ["verify"], invited_by: "coordinator", created_at: "2026-10-25T10:00:00Z", expires_at: "2026-10-28T10:00:00Z", status: "waiting", used_by: null }]
            : [],
        },
      }),
      "POST /api/private/v1/invitations/": (call) => {
        created = true;
        expect(call.body).toEqual({ email: "new@example.org", roles: [1] });
        return { status: 201, body: { id: "00000000-0000-0000-0000-0000000000e1", token: TOKEN, expires_at: "2026-10-28T10:00:00Z" } };
      },
    });
    render(<TeamPeople />, "/workspace/team");
    await userEvent.type(await screen.findByRole("textbox", { name: "Their email address" }), "new@example.org");
    await userEvent.click(screen.getByRole("checkbox", { name: "Verify events and port names" }));
    await userEvent.click(screen.getByRole("button", { name: "Create the invitation link" }));
    expect(await screen.findByText(`http://localhost:3000/invite#${TOKEN}`.replace("http://localhost:3000", window.location.origin))).toBeTruthy();
    expect(await screen.findByText("new@example.org")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Take back the link" })).toBeTruthy();
  });
});
