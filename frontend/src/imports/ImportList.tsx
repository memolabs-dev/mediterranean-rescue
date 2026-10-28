import { api, type ImportSummary, type Me } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Link, navigate, useLocation, withQuery } from "../router";
import { Button } from "../ui/Button";
import { DataTable } from "../ui/DataTable";
import { EmptyState, InlineMessage, PendingState } from "../ui/Feedback";
import { Pagination } from "../ui/Pagination";
import { localDay, sheetLabel } from "./helpers";
import { IMPORTS_PATH, NEW_PATH, PAGE } from "./paths";

export function ImportList({ me }: { me: Me }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { query } = useLocation();
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const list = api.useQuery("get", "/api/private/v1/imports/", { params: { query: { limit: PAGE, offset } } });
  return (
    <>
      <div className="workspace-heading">
        <h1>{t("imports.title")}</h1>
        {me.permissions.stage_snapshot && (
          <Link to={NEW_PATH} className="ui-button ui-button--primary ui-button--md">
            {t("imports.add")}
          </Link>
        )}
      </div>
      <p className="workspace-lead">{t("imports.lead")}</p>
      {list.error ? (
        <InlineMessage tone="error">
          {t("workspace.loadError")}{" "}
          <Button size="sm" onClick={() => void list.refetch()}>
            {t("ui.retry")}
          </Button>
        </InlineMessage>
      ) : !list.data ? (
        <PendingState label={t("workspace.loading")} />
      ) : (
        <>
          <DataTable<ImportSummary>
            caption={t("imports.caption")}
            rows={list.data.items}
            rowId={(item) => item.id}
            busy={list.isFetching}
            empty={
              <EmptyState
                title={t("imports.empty.title")}
                action={
                  me.permissions.stage_snapshot ? (
                    <Link to={NEW_PATH}>{t("imports.add")}</Link>
                  ) : undefined
                }
              >
                <p>{t("imports.empty.body")}</p>
              </EmptyState>
            }
            columns={[
              {
                key: "sheet",
                header: t("imports.col.sheet"),
                render: (item) => <Link to={`${IMPORTS_PATH}/${item.id}`}>{sheetLabel(i18n, item.sheet)}</Link>,
              },
              { key: "date", header: t("imports.col.date"), render: (item) => i18n.date(localDay(item.created_at)) },
              { key: "source", header: t("imports.col.source"), render: (item) => item.source.name },
              { key: "rows", header: t("imports.col.rows"), render: (item) => i18n.number(item.row_count) },
              { key: "by", header: t("imports.col.by"), render: (item) => item.staged_by },
            ]}
          />
          <Pagination
            offset={offset}
            limit={PAGE}
            total={list.data.total_count}
            hasNext={list.data.has_next}
            disabled={list.isFetching}
            onOffsetChange={(next) => navigate(withQuery(IMPORTS_PATH, { offset: next }))}
          />
        </>
      )}
    </>
  );
}

