import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, errorCode, type QueueItem, type ReviewStatus } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Link, matchRoute, navigate, useLocation, withQuery } from "../router";
import { Button } from "../ui/Button";
import { DataTable } from "../ui/DataTable";
import { Dialog } from "../ui/Dialog";
import { EmptyState, InlineMessage, PendingState, StatusLabel } from "../ui/Feedback";
import { FilterBar } from "../ui/FilterBar";
import { Pagination } from "../ui/Pagination";
import { SelectField } from "../ui/SelectField";
import { TextField } from "../ui/TextField";
import { ME_QUERY, WorkspaceShell } from "../workspace/WorkspaceShell";
import { AccessProblem } from "./AccessProblem";
import { codeText, countLabel, kindLabel, RowReview, serverMessageKey } from "./RowReview";

const PAGE = 25;
const STATUSES: readonly ReviewStatus[] = ["to_review", "blocked", "linked"];
export const REVIEW_PATH = "/workspace/review";
const ROW_PATTERN = `${REVIEW_PATH}/:snapshot/rows/:row`;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function readStatus(value: string | null): ReviewStatus {
  return STATUSES.includes(value as ReviewStatus) ? (value as ReviewStatus) : "to_review";
}

function readRoute(pathname: string) {
  const params = matchRoute(ROW_PATTERN, pathname);
  return params?.snapshot && params.row && UUID.test(params.snapshot) && UUID.test(params.row)
    ? { snapshot: params.snapshot, row: params.row }
    : null;
}

// Review queue with the row review as an inspector on wide screens, a page on narrow ones.
export function ReviewWorkspace() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  return (
    <WorkspaceShell
      section="review"
      title={t("review.title")}
      className={`review${readRoute(pathname) ? " review--inspecting" : ""}`}
    >
      {() => <ReviewQueue />}
    </WorkspaceShell>
  );
}

function ReviewQueue() {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const { pathname, query } = useLocation();
  const route = readRoute(pathname);
  const status = readStatus(query.get("status"));
  const offset = Math.max(0, Number(query.get("offset")) || 0);

  const snapshots = api.useQuery("get", "/api/private/v1/snapshots/", { params: { query: { limit: 100 } } });
  const requested = route?.snapshot ?? query.get("snapshot");
  const snapshotId = (requested && UUID.test(requested) ? requested : null) ?? snapshots.data?.items[0]?.id ?? null;
  const queue = api.useQuery(
    "get",
    "/api/private/v1/review/rows/",
    { params: { query: { snapshot: snapshotId ?? "", status, limit: PAGE, offset } } },
    { enabled: Boolean(snapshotId) },
  );
  const carry = api.useMutation("post", "/api/private/v1/review/snapshots/{id}/exact-carries/");

  // Selection is page-scoped and reset whenever the visible page changes (DataTable contract).
  const pageKey = `${snapshotId}|${status}|${offset}`;
  const [selection, setSelection] = useState<{ key: string; ids: Set<string> }>({ key: pageKey, ids: new Set() });
  // Only rows that are still unchanged carries on this page stay selected (a row decided in the
  // inspector leaves the selection).
  const eligibleHere = new Set(
    (queue.data?.items ?? []).filter((item) => item.proposal === "exact_carry").map((item) => item.id),
  );
  const selected = new Set(selection.key === pageKey ? [...selection.ids].filter((id) => eligibleHere.has(id)) : []);
  const [carryOpen, setCarryOpen] = useState(false);
  const [carryReason, setCarryReason] = useState("");
  const [carryError, setCarryError] = useState<string | null>(null);
  const [carryResult, setCarryResult] = useState<{ key: string; text: string } | null>(null);


  const listUrl = (values: { status?: ReviewStatus; offset?: number; snapshot?: string | null }) =>
    withQuery(REVIEW_PATH, {
      snapshot: values.snapshot ?? snapshotId,
      status: values.status ?? status,
      offset: values.offset ?? offset,
    });
  const rowUrl = (rowId: string) =>
    withQuery(`${REVIEW_PATH}/${snapshotId}/rows/${rowId}`, { status, offset });

  // A page emptied by decisions moves back to the last page that still has rows.
  const total = queue.data?.total_count;
  useEffect(() => {
    if (total !== undefined && total > 0 && offset >= total) {
      navigate(listUrl({ offset: Math.floor((total - 1) / PAGE) * PAGE }), { replace: true });
    }
    // listUrl depends on the values compared here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [total, offset]);

  const items = queue.data?.items ?? [];
  const counts = queue.data?.counts ?? { to_review: 0, blocked: 0, linked: 0 };
  // The next row after the current one in this list; the next page when this one is done.
  const openNext = () => {
    const position = items.findIndex((item) => item.id === route?.row);
    const next = items.slice(position + 1).find((item) => item.status === "to_review");
    if (next) navigate(rowUrl(next.id));
    else if (queue.data?.has_next) navigate(listUrl({ offset: offset + PAGE }));
    else navigate(listUrl({}));
  };

  const approveCarries = async () => {
    if (!snapshotId || !carryReason.trim()) return;
    try {
      const result = await carry.mutateAsync({
        params: { path: { id: snapshotId } },
        body: { rows: [...selected], reason: carryReason },
      });
      setCarryResult({ key: pageKey, text: t("review.carry.done", { count: result.carried }) });
      setSelection({ key: pageKey, ids: new Set() });
      setCarryOpen(false);
      setCarryReason("");
      setCarryError(null);
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/review/rows/"] });
    } catch (error) {
      const code = errorCode(error);
      // Shown inside the dialog, where the user is; the list is read again so a retry uses
      // the current state.
      setCarryError(t(serverMessageKey(code)));
      if (code === "conflict") void queue.refetch();
      if (code === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ME_QUERY });
    }
  };

  // The Google Sheets tab in words; its technical name only when no translation exists.
  const sheetName = (sheet: string) => {
    const key = `explore.sheet.${sheet}` as Parameters<typeof t>[0];
    const label = t(key);
    return label === key ? sheet : label;
  };
  const snapshotOptions = (snapshots.data?.items ?? []).map((item) => ({
    value: item.id,
    label: t("review.snapshotLabel", {
      sheet: item.source.key === "sos-logbook" ? t("logbook.sourceName") : sheetName(item.sheet),
      date: i18n.date(item.created_at.slice(0, 10)),
      count: item.row_count,
    }),
  }));

  return (
    <>
      <h1>{t("review.title")}</h1>
      <div className="review__layout">
        <section className="review__queue" aria-labelledby="queue-title">
          <h2 id="queue-title" className="sr-only">
            {t("review.queue")}
          </h2>
          <FilterBar<ReviewStatus>
            legend={t("review.show")}
            value={status}
            onValueChange={(value) => navigate(listUrl({ status: value, offset: 0 }))}
            facets={STATUSES.map((value) => ({ value, label: t(`review.status.${value}`), count: counts[value] }))}
          >
            {snapshotOptions.length > 0 && snapshotId && (
              <SelectField<string>
                label={t("review.export")}
                value={snapshotId}
                options={snapshotOptions}
                onValueChange={(value) => value && navigate(listUrl({ snapshot: value, status: "to_review", offset: 0 }))}
              />
            )}
          </FilterBar>
          {carryResult?.key === pageKey && <InlineMessage tone="success">{carryResult.text}</InlineMessage>}
          {selected.size > 0 && (
            <div className="review-bulk">
              <span>{t("review.carry.selected", { count: selected.size })}</span>
              <Button variant="primary" onClick={() => setCarryOpen(true)}>
                {t("review.carry.open", { count: selected.size })}
              </Button>
            </div>
          )}
          {snapshots.error ? (
            <InlineMessage tone="error">
              {t("review.loadError")}{" "}
              <Button size="sm" onClick={() => void snapshots.refetch()}>
                {t("ui.retry")}
              </Button>
            </InlineMessage>
          ) : queue.error && errorCode(queue.error) === "not_authenticated" ? (
            <AccessProblem code="not_authenticated" />
          ) : snapshots.isSuccess && !snapshotId ? (
            <EmptyState title={t("review.noExport.title")}>
              <p>{t("review.noExport.body")}</p>
            </EmptyState>
          ) : queue.error ? (
            <InlineMessage tone="error">
              {t("review.loadError")}{" "}
              <Button size="sm" onClick={() => void queue.refetch()}>
                {t("ui.retry")}
              </Button>
            </InlineMessage>
          ) : !queue.data ? (
            <PendingState label={t("review.loading")} />
          ) : (
            <DataTable<QueueItem>
              caption={t("review.caption", { status: t(`review.status.${status}`) })}
              rows={items}
              rowId={(item) => item.id}
              activeId={route?.row ?? null}
              busy={queue.isFetching}
              empty={
                <EmptyState title={t(status === "to_review" ? "review.empty.done" : "review.empty.none")}>
                  {status === "to_review" && counts.linked > 0 && (
                    <Link to={listUrl({ status: "linked", offset: 0 })}>{t("review.empty.seeLinked")}</Link>
                  )}
                </EmptyState>
              }
              selection={
                status === "to_review"
                  ? {
                      isEligible: (item) => item.proposal === "exact_carry",
                      selected,
                      onChange: (ids) => setSelection({ key: pageKey, ids }),
                      rowLabel: (item) =>
                        t("review.carry.rowLabel", {
                          date: item.occurred_on ? i18n.date(item.occurred_on) : t("review.unreadable"),
                          kind: kindLabel(i18n, item.kind),
                        }),
                    }
                  : undefined
              }
              columns={[
                {
                  key: "event",
                  header: t("review.col.event"),
                  // Named by what happened and when; the sheet row is only a way to find it in Google Sheets.
                  render: (item) => (
                    <Link to={rowUrl(item.id)} aria-current={item.id === route?.row ? "page" : undefined}>
                      {t("review.rowTitle", {
                        date: item.occurred_on ? i18n.date(item.occurred_on) : t("review.unreadable"),
                        kind: kindLabel(i18n, item.kind),
                      })}
                    </Link>
                  ),
                },
                { key: "count", header: t("review.col.count"), render: (item) => countLabel(i18n, item) },
                {
                  key: "proposal",
                  header: t("review.col.proposal"),
                  render: (item) =>
                    item.proposal === "repeat"
                      ? t("review.proposalShort.repeat", { line: item.repeats_line ?? "?" })
                      : item.status === "blocked"
                      ? item.error_codes.map((code) => codeText(i18n, code)).join(" ")
                      : t(`review.proposalShort.${item.proposal}` as Parameters<typeof t>[0], {
                          count: item.candidate_count,
                        }),
                },
                {
                  key: "status",
                  header: t("review.col.status"),
                  render: (item) => (
                    <StatusLabel
                      status={item.status === "to_review" ? "needsReview" : item.status === "blocked" ? "blocked" : "linked"}
                    />
                  ),
                },
              ]}
            />
          )}
          {queue.data && (
            <Pagination
              offset={offset}
              limit={PAGE}
              total={queue.data.total_count}
              hasNext={queue.data.has_next}
              disabled={queue.isFetching}
              onOffsetChange={(next) => navigate(listUrl({ offset: next }))}
            />
          )}
        </section>
        {route && snapshotId && (
          <section className="review__inspector" aria-label={t("review.inspector")}>
            <RowReview
              key={route.row}
              rowId={route.row}
              snapshotId={snapshotId}
              onClose={() => navigate(listUrl({}))}
              onDecided={(next) => {
                if (next) openNext();
              }}
            />
          </section>
        )}
      </div>
      <Dialog
        title={t("review.carry.title", { count: selected.size })}
        description={t("review.carry.body")}
        open={carryOpen}
        onOpenChange={setCarryOpen}
      >
        <form
          className="review-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void approveCarries();
          }}
        >
          {carryError && <InlineMessage tone="error">{carryError}</InlineMessage>}
          <p className="review-note">
            {t("review.carry.lines", {
              lines: items
                .filter((item) => selected.has(item.id))
                .map((item) => item.line)
                .join(", "),
            })}
          </p>
          <TextField
            label={t("review.reason")}
            value={carryReason}
            onChange={(event) => setCarryReason(event.target.value)}
            error={carry.isError && !carryReason.trim() ? t("review.error.reason") : null}
          />
          <div className="ui-dialog__actions">
            <Button onClick={() => setCarryOpen(false)}>{t("ui.cancel")}</Button>
            <Button type="submit" variant="primary" loading={carry.isPending} disabled={!carryReason.trim()}>
              {t("review.carry.confirm", { count: selected.size })}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
