// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { AboutPage } from "./AboutPage";
import { Welcome } from "./Welcome";

const SIGNED_OUT = {
  "GET /api/private/v1/me/": () => ({ status: 401, body: { code: "not_authenticated", detail: "x" } }),
};

function renderPage(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("about the data", () => {
  it("answers a newcomer's questions in order and says the site is independent", async () => {
    fakeServer(SIGNED_OUT);
    renderPage(<AboutPage />);
    expect(screen.getByRole("heading", { level: 1, name: "About the data" })).toBeTruthy();
    for (const name of ["What you should know", "How to read the map", "What the words mean", "From the sea to this page", "Cite and reuse"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.getByText(/It is not the official website of SOS MEDITERRANEE/)).toBeTruthy();
    expect(screen.getByText("Rescue operation")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Explore the map" }).getAttribute("href")).toBe("/");
    expect(await screen.findByRole("link", { name: "Team sign-in" })).toBeTruthy();
  });

  it("the first-visit card can be closed and stays closed on this browser", async () => {
    renderPage(<Welcome />);
    expect(screen.getByRole("heading", { name: "New here? Three things to know" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Read about the data/ }).getAttribute("href")).toBe("/about");
    const toggle = screen.getByRole("button", { name: "Read the three essential points" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Hide the essential points" }).getAttribute("aria-expanded")).toBe("true");
    await userEvent.click(screen.getByRole("button", { name: "Hide the essential points" }));
    expect(screen.getByRole("button", { name: "Read the three essential points" }).getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(screen.getByRole("button", { name: "Close the introduction" }));
    expect(screen.queryByRole("heading", { name: "New here? Three things to know" })).toBeNull();
    expect(window.localStorage.getItem("welcome-dismissed")).toBe("1");
  });
});
