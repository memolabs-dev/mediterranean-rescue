import type { PortLabel, PortRef } from "../api/client";
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

export function portListState(i18n: I18n, item: PortLabel) {
  const row = item.port_list_row;
  if (!row) return i18n.t("ports.list.absent");
  if (row.position && row.error_codes.length === 0) return i18n.t("ports.list.positioned");
  return i18n.t("ports.list.unclear");
}

export function readingText(i18n: I18n, item: PortLabel) {
  const reading = item.reading;
  if (!reading) return "";
  if (reading.interpretation === "vessel") return i18n.t("ports.reading.vessel", { name: reading.vessel?.name ?? "" });
  if (reading.interpretation === "not_a_port") return i18n.t("ports.reading.not_a_port");
  return i18n.t("ports.reading.ports", { names: reading.ports.map((port) => portName(i18n, port)).join(", ") });
}

