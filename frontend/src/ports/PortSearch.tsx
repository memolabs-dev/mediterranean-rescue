import { errorCode, fetchClient, type PortRef } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { SearchCombobox } from "../ui/SearchCombobox";
import { coordinates, portName } from "./portFormat";

export function PortSearch({ label, value, onValueChange }: { label: string; value: PortRef | null; onValueChange: (port: PortRef | null) => void }) {
  const i18n = useI18n();
  return (
    <SearchCombobox<PortRef>
      label={label}
      startHint={i18n.t("ports.searchHint")}
      value={value}
      onValueChange={onValueChange}
      itemId={(item) => item.id}
      itemLabel={(item) => portName(i18n, item)}
      renderItem={(item) => (
        <span>
          {portName(i18n, item)}
          {item.position && <span className="review-note"> · {coordinates(i18n, item.position)}</span>}
        </span>
      )}
      search={async (q, signal) => {
        const { data, error } = await fetchClient.GET("/api/private/v1/ports/", { params: { query: { q, limit: 20 } }, signal });
        if (error) throw new Error(errorCode(error));
        return data.items;
      }}
    />
  );
}
