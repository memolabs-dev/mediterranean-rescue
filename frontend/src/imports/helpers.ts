import type { I18n } from "../i18n/I18nProvider";

export type Key = Parameters<I18n["t"]>[0];

export function sheetLabel(i18n: I18n, sheet: string) {
  const key = `imports.sheet.${sheet}` as Key;
  const label = i18n.t(key);
  return label === key ? sheet : label;
}

/** Calendar day of a timestamp where the reader is (an import at 01:00 in Paris is that day). */
export function localDay(timestamp: string) {
  const date = new Date(timestamp);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Plain explanation of a diagnostic code; unknown codes are shown as they are. */
export function issueText(i18n: I18n, code: string) {
  const key = `diag.code.${code}` as Key;
  const text = i18n.t(key);
  return text === key ? code : text;
}

