import { api } from "../api/client";
import type { components } from "../api/schema";
import { Explore } from "../explore/Explore";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { Icon } from "../ui/Icon";
import { ErrorBoundary } from "./ErrorBoundary";
import { WorkspaceShell } from "./WorkspaceShell";

type Key = Parameters<I18n["t"]>[0];

/** "3 minutes ago", from the reader's clock; the full date stays in the title attribute. */
function ago(i18n: I18n, timestamp: string, now: number) {
  const minutes = Math.max(0, Math.round((now - new Date(timestamp).getTime()) / 60000));
  const format = new Intl.RelativeTimeFormat(i18n.locale, { numeric: "auto" });
  if (minutes < 60) return format.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 48) return format.format(-hours, "hour");
  return format.format(-Math.round(hours / 24), "day");
}

function SyncStatus() {
  const i18n = useI18n();
  const { t } = i18n;
  // Read again every minute, so "read 3 minutes ago" stays true while the page is open.
  const status = api.useQuery("get", "/api/private/v1/sync/", {}, { refetchInterval: 60_000 });
  const sheets = (status.data?.sheets ?? []).filter((sheet) => sheet.sheet !== "Data_ports");
  if (status.error) return <p className="sync-card sync-card--error">{t("sync.loadError")}</p>;
  if (!status.data) return null;
  if (sheets.length === 0) {
    return (
      <section className="sync-card" aria-labelledby="sync-title">
        <h2 id="sync-title">{t("sync.title")}</h2>
        <p>{t("sync.never")}</p>
      </section>
    );
  }
  // The time the status was received is the reference, so rendering stays pure.
  const now = status.dataUpdatedAt;
  return (
    <section className="sync-card" aria-labelledby="sync-title">
      <h2 id="sync-title">{t("sync.title")}</h2>
      <p className="sync-card__lead">{t("sync.lead")}</p>
      <ul className="sync-card__list">
        {sheets.map((sheet) => {
          const change = sheet.last_change;
          const failing = sheet.last_status === "failed" || sheet.last_status === "refused";
          return (
            <li key={sheet.sheet} className={failing ? "sync-card__item sync-card__item--warn" : "sync-card__item"}>
              <span className="sync-card__name">
                {sheet.source_key === "sos-logbook" ? t("logbook.sourceName") : t(`explore.sheet.${sheet.sheet}` as Key)}
                {sheet.source_key === "sos-logbook" && <span className="sync-card__source"> · {t("logbook.syncEvery")}</span>}
              </span>
              <span title={new Date(sheet.last_checked_at).toLocaleString(i18n.locale)}>
                <Icon name={failing ? "alert" : "check"} size={15} />{" "}
                {t(`sync.status.${sheet.last_status}` as Key, { when: ago(i18n, sheet.last_checked_at, now) })}
              </span>
              {sheet.last_change_at && (
                <span className="sync-card__change">
                  {t("sync.lastChange", { when: ago(i18n, sheet.last_change_at, now) })}{" "}
                  {t("sync.counts", {
                    look: change.to_look_at ?? 0,
                    fix: change.to_fix ?? 0,
                    same: change.unchanged ?? 0,
                  })}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

type Overview = components["schemas"]["LogbookOverview"];

// The rebuilt rows against the figures SOS published. Green only when every compared figure
// is the same; a gap is shown as a gap to reconcile, never as checked (audit of 25 October 2026).
function FiguresCheck({ data }: { data: Overview }) {
  const i18n = useI18n();
  const { t } = i18n;
  const yearGaps = data.years.map((year) => (year.reported === null ? 0 : year.reported - year.in_sheet - year.from_logbook));
  const total = data.cumulative ? data.cumulative.in_sheet + data.cumulative.from_logbook : 0;
  const totalGap = data.cumulative ? data.cumulative.reported - total : 0;
  // The title names the largest difference, so a matching total never hides a year that differs.
  const gap = Math.max(Math.abs(totalGap), ...yearGaps.map(Math.abs));
  const matches = gap === 0;
  const sameOrGap = (reported: number, difference: number, same: Key, differs: Key, surplus: Key) =>
    t(difference === 0 ? same : difference > 0 ? differs : surplus, {
      reported: i18n.number(reported),
      gap: i18n.number(Math.abs(difference)),
    });
  return (
    <div className={`logbook-card__check${matches ? "" : " logbook-card__check--gap"}`}>
      <p className="logbook-card__check-title">
        <Icon name={matches ? "check" : "alert"} size={16} />{" "}
        {matches ? t("logbook.card.checkMatches") : t("logbook.card.checkGapTitle", { count: gap })}
      </p>
      <ul>
        {data.years.map((year, index) => (
          <li key={year.year}>
            {t("logbook.card.checkYear", {
              year: String(year.year),
              total: i18n.number(year.in_sheet + year.from_logbook),
              sheet: i18n.number(year.in_sheet),
              logbook: i18n.number(year.from_logbook),
            })}
            {" · "}
            {year.reported === null
              ? t("logbook.card.checkNone")
              : sameOrGap(year.reported, yearGaps[index]!, "logbook.card.checkSame", "logbook.card.checkGap", "logbook.card.checkSurplus")}
          </li>
        ))}
        {data.cumulative && (
          <li>
            {t("logbook.card.checkTotal", {
              date: i18n.date(data.cumulative.as_of),
              total: i18n.number(total),
              sheet: i18n.number(data.cumulative.in_sheet),
              logbook: i18n.number(data.cumulative.from_logbook),
            })}
            {" · "}
            {sameOrGap(data.cumulative.reported, totalGap, "logbook.card.checkTotalSame", "logbook.card.checkTotalGap", "logbook.card.checkTotalSurplus")}
          </li>
        )}
      </ul>
      {!matches && (
        <p className="logbook-card__check-note">
          {data.cumulative && data.cumulative.in_sheet === 0 ? t("logbook.card.checkNoSheet") : t("logbook.card.checkGapNote")}
        </p>
      )}
      {data.cumulative && data.cumulative.after > 0 && (
        <p className="logbook-card__check-note">
          {t("logbook.card.checkAfter", { count: data.cumulative.after, date: i18n.date(data.cumulative.as_of) })}
        </p>
      )}
      <a href={data.reports_url} target="_blank" rel="noreferrer">
        {t("logbook.card.reports")}
      </a>
    </div>
  );
}

// The public logbook as the way to bring SOS's map up to date (ADR 0014): how far the sheet lags,
// what was rebuilt, what is verified, and the verified rows to paste into the sheet.
export function LogbookCard() {
  const i18n = useI18n();
  const { t } = i18n;
  const overview = api.useQuery("get", "/api/private/v1/logbook/", {});
  const data = overview.data;
  if (overview.error || !data || data.rows === 0) return null;
  return (
    <section className="logbook-card" aria-labelledby="logbook-card-title">
      <p className="logbook-card__eyebrow">{t("logbook.card.eyebrow")}</p>
      <h2 id="logbook-card-title">{t("logbook.card.title", { date: i18n.date(data.sheet_last_date) })}</h2>
      <p className="logbook-card__lead">
        {t("logbook.card.lead", {
          rows: data.rows,
          people: i18n.number(data.people),
          from: data.first_date ? i18n.date(data.first_date) : "…",
          to: data.last_date ? i18n.date(data.last_date) : "…",
        })}
      </p>
      <ol className="logbook-card__steps">
        <li>
          <b>{t("logbook.card.step1")}</b> {t("logbook.card.step1Body", { count: data.to_verify })}
          {data.to_check > 0 && ` ${t("logbook.card.toCheck", { count: data.to_check })}`}
        </li>
        <li>
          <b>{t("logbook.card.step2")}</b> {t("logbook.card.step2Body", { count: data.ready })}
          {data.in_sheet > 0 && ` ${t("logbook.card.inSheet", { count: data.in_sheet })}`}
          {data.not_for_sheet > 0 && ` ${t("logbook.card.notForSheet", { count: data.not_for_sheet })}`}
        </li>
        <li>
          <b>{t("logbook.card.step3")}</b> {t("logbook.card.step3Body")}
        </li>
      </ol>
      {data.years.length > 0 && <FiguresCheck data={data} />}
      <div className="logbook-card__actions">
        {data.to_verify > 0 && data.snapshot && (
          <Link to={`/workspace/review?snapshot=${data.snapshot}`} className="pill-button pill-button--primary">
            <Icon name="check" size={16} />
            {t("logbook.card.verify", { count: data.to_verify })}
          </Link>
        )}
        <Link to="/workspace/data?source=sos-logbook" className="pill-button" onClick={showOnMap}>
          <Icon name="map" size={16} />
          {t("logbook.card.show")}
        </Link>
        {data.ready > 0 ? (
          <a className="pill-button" href="/api/private/v1/logbook/export/" download>
            <Icon name="download" size={16} />
            {t("logbook.card.download", { count: data.ready })}
          </a>
        ) : (
          <span className="logbook-card__disabled">{t("logbook.card.nothingToDownload")}</span>
        )}
      </div>
    </section>
  );
}

// The team's own view of the latest data received, kept out of the public page.
// The map is further down the same page: after filtering, bring it into view, or the click
// seems to do nothing (Guillaume, 25 October 2026).
function showOnMap() {
  requestAnimationFrame(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    document.getElementById("team-explore")?.scrollIntoView?.({ behavior: reduce ? "auto" : "smooth", block: "start" });
  });
}

export function TeamData() {
  const { t } = useI18n();
  return (
    <WorkspaceShell section="data" title={t("workspace.section.data")} className="review review--wide">
      {() => (
        <>
          <LogbookCard />
          <SyncStatus />
          <div id="team-explore">
            <ErrorBoundary fallback={(error, info) => (
              <div style={{ padding: 24, color: "#b00" }}>
                <h2>Explore render error</h2>
                <pre>{error.message}</pre>
                <pre>{info.componentStack}</pre>
              </div>
            )}>
              <Explore audience="team" />
            </ErrorBoundary>
          </div>
        </>
      )}
    </WorkspaceShell>
  );
}
