// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeServer } from "../test/fakeServer";
import { renderWithI18n } from "../test/render";
import { TeamPractice } from "./TeamPractice";
import { journeyDone } from "./journey";

const ME = {
  username: "newcomer",
  decisions: 0,
  permissions: { review_identity: true, stage_snapshot: false, prepare_drafts: false, publish: false, invite: false },
};

afterEach(() => vi.unstubAllGlobals());

describe("practice", () => {
  it("teaches the gesture on an invented operation and sends nothing", async () => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/workspace/practice");
    const { calls } = fakeServer({ "GET /api/private/v1/me/": () => ({ body: ME }) });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderWithI18n(
      <QueryClientProvider client={client}>
        <TeamPractice />
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Yes, everything matches" }));
    expect(screen.getByText(/Look again at the number of people/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "No, something is wrong" }));
    await userEvent.click(screen.getByRole("button", { name: "I mark it verified anyway" }));
    expect(screen.getByText(/A wrong row is never marked verified/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Decide later/ }));
    expect(screen.getByRole("heading", { name: "That is all there is to it" })).toBeTruthy();
    expect(journeyDone("practice", "newcomer")).toBe(true);
    expect(journeyDone("practice", "another-volunteer")).toBe(false);
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });
});
