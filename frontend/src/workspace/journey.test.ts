// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { journeyDone, journeyStorageKey, markJourney } from "./journey";

beforeEach(() => window.localStorage.clear());

describe("account-scoped onboarding", () => {
  it("remembers a step only for the signed-in volunteer", () => {
    markJourney("practice", "volunteer.one@example.org");
    expect(journeyDone("practice", "volunteer.one@example.org")).toBe(true);
    expect(journeyDone("practice", "volunteer.two@example.org")).toBe(false);
    expect(journeyDone("publishGuide", "volunteer.one@example.org")).toBe(false);
    const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index));
    expect(keys).toHaveLength(1);
    expect(keys[0]).not.toContain("volunteer.one@example.org");
  });

  it("ignores the legacy browser-global flags to prevent inherited progress", () => {
    window.localStorage.setItem("team-practice-done", "1");
    window.localStorage.setItem("team-publish-guide-seen", "1");
    expect(journeyDone("practice", "invited-person")).toBe(false);
    expect(journeyDone("publishGuide", "invited-person")).toBe(false);
  });

  it("does not write without an authenticated identity", () => {
    markJourney("practice", "");
    expect(journeyDone("practice", "")).toBe(false);
    expect(window.localStorage.length).toBe(0);
  });

  it("separates Unicode usernames and stays stable across pages", () => {
    const first = journeyStorageKey("practice", "élève");
    expect(first).toBe(journeyStorageKey("practice", "élève"));
    expect(first).not.toBe(journeyStorageKey("practice", "eleve"));
    markJourney("intro", "élève");
    expect(journeyDone("intro", "élève")).toBe(true);
    expect(journeyDone("intro", "eleve")).toBe(false);
  });
});
