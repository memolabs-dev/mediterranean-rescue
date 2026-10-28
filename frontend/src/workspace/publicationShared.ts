import { errorCode } from "../api/client";
import type { I18n } from "../i18n/I18nProvider";

// All publication mutations are server-authorized. The UI must not infer rights
// from locally cached public events or bypass the protected private endpoints.
export type Key = Parameters<I18n["t"]>[0];
export type Status = "draft" | "published" | "withdrawn";
export const STATUSES: readonly Status[] = ["draft", "published", "withdrawn"];
export const PAGE = 25;
export const OVERVIEW = ["get", "/api/private/v1/publication/"] as const;

export function failure(t: I18n["t"], error: unknown): string {
  const code = errorCode(error);
  if (code === "rights_not_approved") return t("publish.error.rights");
  if (code === "conflict") return t("publish.error.conflict");
  if (code === "permission_denied") return t("publish.error.denied");
  if (code === "not_authenticated") return t("publish.error.signedOut");
  return t("publish.error.other");
}
