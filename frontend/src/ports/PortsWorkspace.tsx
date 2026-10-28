import { api, type PortLabel, type PortLabelStatus } from "../api/client";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { Link, matchRoute, navigate, useLocation, withQuery } from "../router";
import { Button } from "../ui/Button";
import { DataTable } from "../ui/DataTable";
import { EmptyState, InlineMessage, PendingState, StatusLabel } from "../ui/Feedback";
import { FilterBar } from "../ui/FilterBar";
import { Pagination } from "../ui/Pagination";
import { WorkspaceShell } from "../workspace/WorkspaceShell";
import { LabelReading } from "./LabelReading";
import { portName } from "./portFormat";

export const PORTS_PATH = "/workspace/ports";
const LABEL_PATTERN = `${PORTS_PATH}/labels/:id`;
const LABEL_ID = /^[0-9a-f]{32}$/;
const STATUSES: readonly PortLabelStatus[] = ["to_read", "read"];
const PAGE = 25;

function readStatus(value: string | null): PortLabelStatus {
  return STATUSES.includes(value as PortLabelStatus) ? (value as PortLabelStatus) : "to_read";
}

function readLabelId(pathname: string) {
  const id = matchRoute(LABEL_PATTERN, pathname)?.id;
  return id && LABEL_ID.test(id) ? id : null;
}

// Parcours C: W06 (names to read) with W07 (read one name) beside it on wide screens.
export function PortsWorkspace() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const labelId = readLabelId(pathname);
  return (
    <WorkspaceShell section="ports" title={t("ports.title")} className={`review${labelId ? " review--inspecting" : ""}`}>
      {() => <PortLabels labelId={labelId} />}
    </WorkspaceShell>
  );
}

function PortLabels({ labelId }: { labelId: string | null }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { query } = useLocation();
  const status = readStatus(query.get("status"));
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const labels = api.useQuery("get", "/api/private/v1/ports/labels/", { params: { query: { status, limit: PAGE, offset } } });
  const listUrl = (values: { status?: PortLabelStatus; offset?: number }) =>
    withQuery(PORTS_PATH, { status: values.status ?? status, offset: values.offset ?? offset });
  const labelUrl = (id: string) => withQuery(`${PORTS_PATH}/labels/${id}`, { status, offset });
  const items = labels.data?.items ?? [];
  const counts = labels.data?.counts ?? { to_read: 0, read: 0 };

  const openNext = () => {
    const position = items.findIndex((item) => item.id === labelId);
    const next = items.slice(position + 1).find((item) => item.status === "to_read") ?? items.find((item) => item.status === "to_read" && item.id !== labelId);
    navigate(next ? labelUrl(next.id) : listUrl({}));
  };

  return (
    <>
      <h1>{t("ports.title")}</h1>
      <p className="workspace-lead">{t("ports.lead")}</p>
      <div className="review__layout">
        <section className="review__queue" aria-labelledby="labels-title">
          <h2 id="labels-title" className="sr-only">
            {t("ports.list")}
          </h2>
          <FilterBar<PortLabelStatus>
            legend={t("review.show")}
            value={status}
            onValueChange={(value) => navigate(listUrl({ status: value, offset: 0 }))}
            facets={STATUSES.map((value) => ({ value, label: t(`ports.status.${value}`), count: counts[value] }))}
          />
          {labels.error ? (
            <InlineMessage tone="error">
              {t("workspace.loadError")}{" "}
              <Button size="sm" onClick={() => void labels.refetch()}>
                {t("ui.retry")}
              </Button>
            </InlineMessage>
          ) : !labels.data ? (
            <PendingState label={t("workspace.loading")} />
          ) : (
            <DataTable<PortLabel>
              caption={t("ports.caption", { status: t(`ports.status.${status}`) })}
              rows={items}
              rowId={(item) => item.id}
              activeId={labelId}
              busy={labels.isFetching}
              empty={
                <EmptyState title={t(status === "to_read" ? "ports.empty.done" : "ports.empty.none")}>
                  {status === "to_read" && <p>{t("ports.empty.doneBody")}</p>}
                </EmptyState>
              }
              columns={[
                {
                  key: "label",
                  header: t("ports.col.label"),
                  render: (item) => (
                    <Link to={labelUrl(item.id)} aria-current={item.id === labelId ? "page" : undefined}>
                      “{item.label}”
                    </Link>
                  ),
                },
                {
                  key: "operations",
                  header: t("ports.col.operations"),
                  numeric: true,
                  render: (item) => i18n.number(item.operations),
                },
                { key: "list", header: t("ports.col.list"), render: (item) => portListState(i18n, item) },
                {
                  key: "reading",
                  header: t("ports.col.reading"),
                  render: (item) =>
                    item.reading ? (
                      readingText(i18n, item)
                    ) : item.suggested_port ? (
                      t("ports.suggestion", { name: item.suggested_port.name })
                    ) : (
                      <StatusLabel status="needsReview" />
                    ),
                },
              ]}
            />
          )}
          {labels.data && (
            <Pagination
              offset={offset}
              limit={PAGE}
              total={labels.data.total_count}
              hasNext={labels.data.has_next}
              disabled={labels.isFetching}
              onOffsetChange={(next) => navigate(listUrl({ offset: next }))}
            />
          )}
        </section>
        {labelId && (
          <section className="review__inspector" aria-label={t("ports.inspector")}>
            <LabelReading key={labelId} id={labelId} onClose={() => navigate(listUrl({}))} onNext={openNext} />
          </section>
        )}
      </div>
    </>
  );
}

function portListState(i18n: I18n, item: PortLabel) {
  const row = item.port_list_row;
  if (!row) return i18n.t("ports.list.absent");
  if (row.position && row.error_codes.length === 0) return i18n.t("ports.list.positioned");
  return i18n.t("ports.list.unclear");
}

function readingText(i18n: I18n, item: PortLabel) {
  const reading = item.reading;
  if (!reading) return "";
  if (reading.interpretation === "vessel") return i18n.t("ports.reading.vessel", { name: reading.vessel?.name ?? "" });
  if (reading.interpretation === "not_a_port") return i18n.t("ports.reading.not_a_port");
  return i18n.t("ports.reading.ports", { names: reading.ports.map((port) => portName(i18n, port)).join(", ") });
}

