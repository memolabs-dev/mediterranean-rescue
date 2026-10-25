// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { VolunteerCredentials } from "./VolunteerCredentials";

function render() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(
    <QueryClientProvider client={client}><VolunteerCredentials /></QueryClientProvider>
  );
}
afterEach(() => vi.unstubAllGlobals());

describe("first invitation sign-in setup", () => {
  it("asks for explicit matching credentials and never submits an invalid pair", async () => {
    const { calls } = fakeServer({
      "GET /api/private/v1/credentials/": () => ({ body: { needs_setup: true } }),
      "GET /api/csrf/": () => ({ body: { csrfToken: "fixture-csrf" } }),
      "POST /api/private/v1/credentials/": () => ({ body: { needs_setup: false } }),
    });
    render();
    expect(await screen.findByRole("heading", { name: "Keep your volunteer access" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Secure my access" }));
    expect(screen.getAllByText(/Use 12 to 128 characters/).length).toBeGreaterThan(0);
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await userEvent.type(screen.getByLabelText("New password"), "LongSyntheticCredential#2026");
    await userEvent.type(screen.getByLabelText("Repeat password"), "not the same");
    await userEvent.click(screen.getByRole("button", { name: "Secure my access" }));
    expect(screen.getByText("Enter the same password twice.")).toBeTruthy();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await userEvent.clear(screen.getByLabelText("Repeat password"));
    await userEvent.type(screen.getByLabelText("Repeat password"), "LongSyntheticCredential#2026");
    await userEvent.click(screen.getByRole("button", { name: "Secure my access" }));
    expect(await screen.findByRole("status")).toBeTruthy();
    const posts = calls.filter((call) => call.method === "POST");
    expect(posts).toHaveLength(1);
    expect(posts[0]?.body).toEqual({
      password: "LongSyntheticCredential#2026",
      confirmation: "LongSyntheticCredential#2026",
    });
  });

  it("hides setup when the current account is ineligible", async () => {
    fakeServer({ "GET /api/private/v1/credentials/": () => ({ body: { needs_setup: false } }) });
    render();
    expect(screen.queryByRole("heading", { name: "Keep your volunteer access" })).toBeNull();
  });

  it("does not expose backend error details", async () => {
    fakeServer({
      "GET /api/private/v1/credentials/": () => ({ body: { needs_setup: true } }),
      "GET /api/csrf/": () => ({ body: { csrfToken: "fixture-csrf" } }),
      "POST /api/private/v1/credentials/": () => ({
        status: 400,
        body: { code: "invalid", detail: "test internal diagnostic" },
      }),
    });
    render();
    await screen.findByRole("heading", { name: "Keep your volunteer access" });
    await userEvent.type(screen.getByLabelText("New password"), "LongSyntheticCredential#2026");
    await userEvent.type(screen.getByLabelText("Repeat password"), "LongSyntheticCredential#2026");
    await userEvent.click(screen.getByRole("button", { name: "Secure my access" }));
    expect(await screen.findByText(/Choose a stronger one/)).toBeTruthy();
    expect(screen.queryByText("test internal diagnostic")).toBeNull();
  });
});
