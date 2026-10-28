import { describe, expect, it, vi } from "vitest";
import { eventParam, motion } from "./navigation";

describe("explore navigation boundary", () => {
  it("accepts only UUID event links and normalizes their case", () => {
    expect(eventParam("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA")).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(eventParam("invalid")).toBeNull();
    expect(eventParam("../api/private/v1/me/")).toBeNull();
    expect(eventParam(null)).toBeNull();
  });

  it("honors reduced motion for keyboard and scroll navigation", () => {
    vi.stubGlobal("window", { matchMedia: () => ({ matches: true }) });
    try {
      expect(motion()).toBe("auto");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
