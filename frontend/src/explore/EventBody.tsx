import { api } from "../api/client";
import { boatLabel } from "./boat";
import { useI18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { formatPosition } from "../shared/geo";
import { Icon } from "../ui/Icon";
import { EvidenceBlock } from "./Evidence";
import { sheetName } from "./labels";
import { isReferenceMapHome } from "./sourceLink";

// The opened record of one event, shared by every view of the main screen.
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function PreviewBody({ id }: { id: string }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { data: row, error } = api.useQuery("get", "/api/private/v1/preview/events/{id}/", { params: { path: { id } } });
  if (error) return <p role="alert">{t("detail.loadError")}</p>;
  if (!row) return <p className="card__loading">{t("detail.loading")}</p>;
  const count = (value: number | null) => (value === null ? t("detail.unknownCount") : i18n.number(value));
  return (
    <>
      <dl className="facts">
        {/* Men too: the sheet has the column, and showing only women and minors read as a gap. */}
        <Fact label={t("preview.detail.men")} value={count(row.men)} />
        <Fact label={t("preview.detail.women")} value={count(row.women)} />
        <Fact label={t("preview.detail.minors")} value={count(row.minors)} />
        {row.sheet === "Other_data" && <Fact label={t("preview.detail.deaths")} value={count(row.deaths)} />}
        <Fact label={t("preview.detail.boat")} value={boatLabel(i18n, row.boat_type) ?? t("detail.notProvided")} />
        <Fact
          label={t("detail.position")}
          value={
            row.position
              ? `${formatPosition(i18n, row.position.latitude, row.position.longitude)}${row.position.inferred_hemisphere && !row.evidence ? ` ${t("explore.positionEstimated")}` : ""}`
              : t("detail.unknownPosition")
          }
        />
        {/* The logbook says nothing about photos: unknown, so not shown as zero. */}
        {!row.evidence && <Fact label={t("preview.detail.photos")} value={i18n.number(row.image_count)} />}
      </dl>
      {row.error_codes.length > 0 && (
        <p className="card__warning">
          <Icon name="alert" size={16} /> {t("preview.status.blocked")}
        </p>
      )}
      {row.evidence ? (
        <EvidenceBlock evidence={row.evidence} />
      ) : (
        <p className="card__provenance">
          {t("explore.whereFrom", { source: row.source.name, date: i18n.date(row.exported_at.slice(0, 10)) })}{" "}
          {t("explore.inSheets", { line: row.line, sheet: sheetName(i18n, row.sheet) })}
        </p>
      )}
      <Link to={`/workspace/review/${row.snapshot}/rows/${row.id}`} className="pill-button pill-button--primary">
        {t("preview.detail.check")}
        <Icon name="arrowRight" size={16} />
      </Link>
    </>
  );
}

/** Only web addresses become links: the server checks them too, this is the second lock. */
function webLink(url: string | null | undefined) {
  return url && /^https?:\/\//i.test(url) ? url : undefined;
}

export function PublicBody({ id }: { id: string }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { data: event, error } = api.useQuery("get", "/api/v1/events/{id}/", { params: { path: { id } } });
  const evidence = api.useQuery("get", "/api/v1/events/{id}/evidence/", { params: { path: { id }, query: { limit: 25, offset: 0 } } });
  if (error) return <p role="alert">{t("detail.loadError")}</p>;
  if (!event) return <p className="card__loading">{t("detail.loading")}</p>;
  return (
    <>
      {event.source.synthetic && <p className="card__warning">{t("detail.trainingData")}</p>}
      <p className="card__summary-text">{event.summary || t("detail.noSummary")}</p>
      <dl className="facts">
        <Fact label={t("detail.vessel")} value={event.vessel?.name ?? t("detail.notProvided")} />
        <Fact label={t("detail.voyage")} value={event.voyage?.title ?? t("detail.notProvided")} />
        <Fact
          label={t("detail.position")}
          value={
            event.position
              ? `${formatPosition(i18n, event.position.latitude, event.position.longitude)} (${t(
                  event.position.precision === "approximate" ? "detail.precision.approximate" : "detail.precision.reported",
                )})`
              : t("detail.unknownPosition")
          }
        />
      </dl>
      <div className="card__sources">
        {webLink(event.source_url) && (
          <a href={webLink(event.source_url)} target="_blank" rel="noreferrer" className="pill-button pill-button--primary">
            {t(isReferenceMapHome(event.source_url) ? "detail.referenceMapLink" : "detail.sourceLink")}
            <Icon name="external" size={16} />
          </a>
        )}
        {(evidence.data?.items ?? [])
          .filter((item) => webLink(item.url))
          .map((item) => (
            <a key={item.url} href={webLink(item.url)} target="_blank" rel="noreferrer" className="pill-button">
              {item.label}
              <Icon name="external" size={16} />
            </a>
          ))}
      </div>
      <p className="card__provenance">
        {event.source.name}. {event.source.license_note}
      </p>
      <p className="card__provenance">{t("detail.countsNote")}</p>
    </>
  );
}

