import { describe, expect, it } from "vitest";
import { isReferenceMapHome } from "./sourceLink";

describe("source link meaning", () => {
  it("labels only the SOS reference map homepage as general context", () => {
    expect(isReferenceMapHome("https://map.sosmediterranee.org/")).toBe(true);
    expect(isReferenceMapHome("https://map.sosmediterranee.org")).toBe(true);
    expect(isReferenceMapHome("http://map.sosmediterranee.org/")).toBe(true);
  });

  it("keeps actual evidence and event-specific links labelled as sources", () => {
    expect(isReferenceMapHome("https://sosmediterranee.org/operation/operation-14-22-august-2026/")).toBe(false);
    expect(isReferenceMapHome("https://map.sosmediterranee.org/?operation=42")).toBe(false);
    expect(isReferenceMapHome("https://map.sosmediterranee.org/#operation-42")).toBe(false);
    expect(isReferenceMapHome("https://example.org/fictional/rescue-001")).toBe(false);
  });

  it("rejects lookalike and malformed addresses", () => {
    expect(isReferenceMapHome("https://map.sosmediterranee.org.evil.invalid/")).toBe(false);
    expect(isReferenceMapHome("javascript:alert(1)")).toBe(false);
    expect(isReferenceMapHome("not a url")).toBe(false);
  });
});
