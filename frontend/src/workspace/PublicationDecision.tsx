import { Button as BaseButton } from "@base-ui/react/button";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, fetchClient } from "../api/client";
import { kindName, peopleText } from "../explore/labels";
import { useI18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { Button } from "../ui/Button";
import { ConfirmationDialog } from "../ui/ConfirmationDialog";
import { DataTable } from "../ui/DataTable";
import { EmptyState, InlineMessage, PendingState } from "../ui/Feedback";
import { Pagination } from "../ui/Pagination";
import { TextField } from "../ui/TextField";
import { failure, OVERVIEW, PAGE, STATUSES, type Key, type Status } from "./publicationShared";

// Second human decision: publish or withdraw only explicitly selected, current,
// rights-approved events. The backend enforces each permission and logs a reason.
export function Decide({
  canPublish,
  counts,
  ready,
  reviewer,
}: {
  canPublish: boolean;
  counts: Record<Status, number>;
  /** Verified events not prepared yet: the empty list then points to step 1. */
  ready: number;
  reviewer: boolean;
}) {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("draft");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const events = api.useQuery("get", "/api/private/v1/publication/events/", {
    params: { query: { status, offset, limit: PAGE } },
  });
  const publish = status !== "published";
  // Only the ticked events still shown count: a refreshed list never carries hidden ones along.
  const chosen = (events.data?.items ?? []).map((item) => item.id).filter((id) => selected.has(id));
  const count = chosen.length;
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["get", "/api/private/v1/publication/events/"],
      }),
      queryClient.invalidateQueries({ queryKey: [...OVERVIEW] }),
    ]);

  const decide = async () => {
    const { data, error } = await fetchClient.POST("/api/private/v1/publication/decisions/", {
      body: {
        action: publish ? "publish" : "withdraw",
        events: chosen,
        reason: reason.trim(),
      },
    });
    if (error) {
      // The dialog stays open with the explanation; the list behind it shows the current state.
      void refresh();
      throw error;
    }
    setSelected(new Set());
    setReason("");
    setOffset(0);
    setDone(
      t(publish ? "publish.decide.published" : "publish.decide.withdrawn", {
        count: data.count,
      }),
    );
    await refresh();
  };

  return (
    <section className="publish-step" aria-labelledby="decide-title">
      <p className="publish-step__eyebrow">{t("publish.step", { number: 2 })}</p>
      <h2 id="decide-title">{t("publish.decide.title")}</h2>
      <p className="publish-step__why">{t("publish.decide.why")}</p>
      <div className="views publish-tabs" role="group" aria-label={t("publish.decide.show")}>
        {STATUSES.map((value) => (
          <BaseButton
            key={value}
            className="views__option"
            aria-pressed={status === value}
            onClick={() => {
              setStatus(value);
              setOffset(0);
              setSelected(new Set());
              setDone(null);
            }}
          >
            {t(`publish.tab.${value}` as Key)} <span className="publish-tabs__count">{counts[value]}</span>
          </BaseButton>
        ))}
      </div>
      {done && <InlineMessage tone="success">{done}</InlineMessage>}
      {!canPublish && <InlineMessage tone="info">{t("publish.decide.notAllowed")}</InlineMessage>}
      {events.error ? (
        <InlineMessage tone="error">{t("workspace.loadError")}</InlineMessage>
      ) : !events.data ? (
        <PendingState label={t("workspace.loading")} />
      ) : (
        <>
          <DataTable
            caption={t(`publish.tab.${status}` as Key)}
            rows={events.data.items}
            rowId={(item) => item.id}
            busy={events.isFetching}
            columns={[
              {
                key: "date",
                header: t("publish.col.date"),
                render: (item) => i18n.date(item.occurred_on),
              },
              {
                key: "event",
                header: t("publish.col.event"),
                render: (item) => (
                  <span>
                    <b>{kindName(i18n, item.kind)}</b> · {peopleText(i18n, item.kind, item.people)}
                  </span>
                ),
              },
              {
                key: "port",
                header: t("publish.col.port"),
                render: (item) => item.port ?? t("explore.logbook.noPort"),
              },
              {
                key: "place",
                header: t("publish.col.place"),
                render: (item) => t(item.located ? "publish.located" : "publish.notLocated"),
              },
            ]}
            selection={
              canPublish
                ? {
                    // An event whose source has not agreed cannot be ticked for publishing.
                    isEligible: (item) => !publish || item.rights_approved,
                    selected,
                    onChange: setSelected,
                    rowLabel: (item) => `${kindName(i18n, item.kind)}, ${i18n.date(item.occurred_on)}`,
                  }
                : undefined
            }
            empty={
              <EmptyState title={t(`publish.empty.${status}.title` as Key)}>
                {status === "draft" && ready > 0 ? (
                  <>
                    <p>{t("publish.empty.ready", { count: ready })}</p>
                    <a href="#prepare-title" className="pill-button">
                      {t("publish.empty.toStep1")}
                    </a>
                  </>
                ) : (
                  <>
                    <p>{t(`publish.empty.${status}.body` as Key)}</p>
                    {status === "draft" && reviewer && (
                      <Link to="/workspace/review" className="pill-button">
                        {t("home.verify.action")}
                      </Link>
                    )}
                  </>
                )}
              </EmptyState>
            }
          />
          {events.data.total_count > 0 && (
            <Pagination
              offset={offset}
              limit={PAGE}
              total={events.data.total_count}
              hasNext={events.data.has_next}
              disabled={events.isFetching}
              onOffsetChange={(next) => {
                setOffset(next);
                setSelected(new Set());
              }}
            />
          )}
          {canPublish && count > 0 && (
            <div className="publish-form publish-form--decision">
              <TextField
                label={t("publish.reason")}
                description={t(publish ? "publish.decide.reasonHelp" : "publish.decide.withdrawHelp")}
                value={reason}
                maxLength={500}
                onChange={(event) => setReason(event.target.value)}
              />
              <ConfirmationDialog
                trigger={
                  <Button variant={publish ? "primary" : "danger"} disabled={!reason.trim()}>
                    {t(publish ? "publish.decide.publish" : "publish.decide.withdraw", { count })}
                  </Button>
                }
                title={t(publish ? "publish.confirm.publishTitle" : "publish.confirm.withdrawTitle", { count })}
                consequence={t(publish ? "publish.confirm.publish" : "publish.confirm.withdraw", { count })}
                confirmLabel={t(publish ? "publish.decide.publish" : "publish.decide.withdraw", { count })}
                danger={!publish}
                onConfirm={decide}
                failureMessage={(error) => failure(t, error)}
              />
            </div>
          )}
        </>
      )}
    </section>
  );
}
