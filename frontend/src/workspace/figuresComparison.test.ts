import { describe, expect, it } from "vitest";
import { assessFigures } from "./figuresComparison";

describe("comparison against SOS reports", () => {
  it("confirms a match only when published reference values are comparable", () => {
    const result = assessFigures({
      years: [{ reported: 42, in_sheet: 40, from_logbook: 2 }],
      cumulative: { reported: 42, in_sheet: 40, from_logbook: 2 },
    });
    expect(result).toMatchObject({ gap: 0, status: "match", hasUnknown: false });
  });

  it("does not turn a missing annual report into a green match", () => {
    const result = assessFigures({
      years: [{ reported: null, in_sheet: 40, from_logbook: 2 }],
      cumulative: { reported: 42, in_sheet: 40, from_logbook: 2 },
    });
    expect(result).toMatchObject({ yearGaps: [null], gap: 0, hasUnknown: true, status: "incomplete" });
  });

  it("treats the absence of any published comparison as unknown", () => {
    expect(assessFigures({ years: [], cumulative: null }).status).toBe("incomplete");
  });

  it("keeps actual gaps visible even when another report is missing", () => {
    const result = assessFigures({
      years: [
        { reported: 45, in_sheet: 40, from_logbook: 2 },
        { reported: null, in_sheet: 20, from_logbook: 3 },
      ],
      cumulative: null,
    });
    expect(result).toMatchObject({ yearGaps: [3, null], gap: 3, hasUnknown: true, status: "gap" });
  });

  it("can reconcile a cumulative report when no annual lines are present", () => {
    expect(assessFigures({
      years: [],
      cumulative: { reported: 6, in_sheet: 5, from_logbook: 1 },
    }).status).toBe("match");
  });
});
