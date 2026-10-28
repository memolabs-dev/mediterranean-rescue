import type { IdentityCandidate } from "../api/client";
import type { I18n } from "../i18n/I18nProvider";

const SERVER_CODES = new Set([
  "conflict",
  "not_authenticated",
  "permission_denied",
  "csrf_failed",
  "invalid",
  "not_found",
  "method_not_allowed",
  "network",
]);

/** Catalog key for a server error code; unknown codes get the generic message. */
export function serverMessageKey(code: string): Parameters<I18n["t"]>[0] {
  return (SERVER_CODES.has(code) ? `review.server.${code}` : "review.server.error") as Parameters<I18n["t"]>[0];
}
export type Summary = IdentityCandidate["summary"];

/** The Google Sheets tab in words; its technical name only when no translation exists. */
export function sheetName(i18n: I18n, sheet: string) {
  const key = `explore.sheet.${sheet}` as Parameters<I18n["t"]>[0];
  const label = i18n.t(key);
  return label === key ? sheet : label;
}

/** A row named by what happened and when ("6 Feb 2024 · Rescue operation"), never by its sheet line. */
export function rowTitle(i18n: I18n, interpreted: unknown) {
  const facts = (interpreted ?? {}) as { occurred_on?: unknown; kind?: unknown };
  return i18n.t("review.rowTitle", {
    date: typeof facts.occurred_on === "string" ? i18n.date(facts.occurred_on) : i18n.t("review.unreadable"),
    kind: kindLabel(i18n, typeof facts.kind === "string" ? facts.kind : null),
  });
}

/** The singular name of one event's kind ("Rescue operation"). */
export function kindLabel(i18n: I18n, kind: string | null | undefined) {
  if (!kind) return i18n.t("review.unknown");
  const key = `kindOne.${kind}` as const;
  const label = i18n.t(key as Parameters<I18n["t"]>[0]);
  return label === key ? kind : label;
}

export function countLabel(i18n: I18n, item: { people: number | null; deaths: number | null }) {
  if (item.people !== null) return i18n.t("events.people", { count: item.people });
  if (item.deaths !== null) return i18n.t("review.deaths", { count: item.deaths });
  return i18n.t("events.peopleUnknown");
}

export function identityLabel(i18n: I18n, candidate: IdentityCandidate) {
  const { summary } = candidate;
  const date = summary.occurred_on ? i18n.date(summary.occurred_on) : i18n.t("review.unknown");
  return `${kindLabel(i18n, summary.kind)} · ${date} · ${countLabel(i18n, summary)} · ${candidate.id.slice(0, 8)}`;
}

/** A diagnostic code in words; the code itself when the catalog has no sentence for it. */
export function codeText(i18n: I18n, code: string) {
  const key = `diag.code.${code}` as Parameters<I18n["t"]>[0];
  const text = i18n.t(key);
  return text === key ? code : text;
}

