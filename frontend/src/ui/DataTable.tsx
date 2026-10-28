import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { Checkbox } from "./Checkbox";

export interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  numeric?: boolean;
}

export interface TableSelection<T> {
  /** Only eligible rows get a checkbox; the header box selects the eligible rows of this page. */
  isEligible: (item: T) => boolean;
  selected: ReadonlySet<string>;
  onChange: (selected: Set<string>) => void;
  rowLabel: (item: T) => string;
}

export interface DataTableProps<T> {
  caption: string;
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowId: (item: T) => string;
  /** Highlights the row being inspected. */
  activeId?: string | null;
  selection?: TableSelection<T> | undefined;
  busy?: boolean;
  empty?: ReactNode;
}

// A semantic table: caption, column headers, a dedicated title control per row, no grid
// keyboard model. Selection never extends beyond the visible page (contract C15).
export function DataTable<T>({ caption, columns, rows, rowId, activeId, selection, busy, empty }: DataTableProps<T>) {
  const { t } = useI18n();
  const eligible = selection ? rows.filter(selection.isEligible).map(rowId) : [];
  const selectedHere = eligible.filter((id) => selection?.selected.has(id));
  const toggleAll = (checked: boolean) => selection?.onChange(new Set(checked ? eligible : []));
  const toggle = (id: string, checked: boolean) => {
    if (!selection) return;
    const next = new Set(selection.selected);
    if (checked) next.add(id);
    else next.delete(id);
    selection.onChange(next);
  };

  if (!rows.length && empty) return <>{empty}</>;
  return (
    <div className="ui-table">
      {selection && eligible.length > 0 && (
        <p className="ui-table__selection" role="status">
          {t("ui.table.selected", { count: selectedHere.length })}
        </p>
      )}
      <table aria-busy={busy || undefined}>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {selection && (
              <th scope="col" className="ui-table__select">
                {eligible.length > 0 && (
                  <Checkbox
                    hideLabel
                    label={t("ui.table.selectPage", { count: eligible.length })}
                    checked={selectedHere.length > 0 && selectedHere.length === eligible.length}
                    indeterminate={selectedHere.length > 0 && selectedHere.length < eligible.length}
                    onCheckedChange={toggleAll}
                  />
                )}
              </th>
            )}
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.numeric ? "ui-table__numeric" : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => {
            const id = rowId(item);
            return (
              <tr key={id} data-row-id={id} aria-current={id === activeId ? "true" : undefined}>
                {selection && (
                  <td className="ui-table__select">
                    {selection.isEligible(item) && (
                      <Checkbox
                        hideLabel
                        label={selection.rowLabel(item)}
                        checked={selection.selected.has(id)}
                        onCheckedChange={(checked) => toggle(id, checked)}
                      />
                    )}
                  </td>
                )}
                {columns.map((column) => (
                  <td key={column.key} className={column.numeric ? "ui-table__numeric" : undefined}>
                    {column.render(item)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
