// Never mark data as reconciled when the association has not published a comparable
// reference figure. A missing report is unknown, not a zero-person difference.
export interface FiguresData {
  years: readonly { reported: number | null; in_sheet: number; from_logbook: number }[];
  cumulative?: { reported: number; in_sheet: number; from_logbook: number } | null;
}

export function assessFigures(data: FiguresData) {
  const yearGaps = data.years.map((year) =>
    year.reported === null ? null : year.reported - year.in_sheet - year.from_logbook,
  );
  const total = data.cumulative ? data.cumulative.in_sheet + data.cumulative.from_logbook : 0;
  const totalGap = data.cumulative ? data.cumulative.reported - total : null;
  const compared = yearGaps.filter((gap): gap is number => gap !== null);
  if (totalGap !== null) compared.push(totalGap);
  const gap = Math.max(0, ...compared.map((difference) => Math.abs(difference)));
  const hasUnknown = yearGaps.some((difference) => difference === null);
  const status = gap > 0 ? "gap" : hasUnknown || compared.length === 0 ? "incomplete" : "match";
  return { yearGaps, total, totalGap, gap, hasUnknown, status } as const;
}
