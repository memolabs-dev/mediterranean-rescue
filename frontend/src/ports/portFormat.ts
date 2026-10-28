import type { PortRef } from "../api/client";
import type { I18n } from "../i18n/I18nProvider";

export function coordinates(i18n: I18n, position: { longitude: number; latitude: number }) {
  const format = (value: number) => new Intl.NumberFormat(i18n.locale, { maximumFractionDigits: 4 }).format(value);
  return i18n.t("ports.position", { latitude: format(position.latitude), longitude: format(position.longitude) });
}

export function portName(i18n: I18n, port: PortRef) {
  return port.country_code ? `${port.name} (${port.country_code})` : port.name;
}

/** A decimal typed with a dot or a comma, or null. */
export function parseDecimal(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return null;
  return Number(normalized);
}

