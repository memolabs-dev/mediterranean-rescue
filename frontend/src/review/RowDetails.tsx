import { useState } from "react";
import type { RowDetail } from "../api/client";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { formatPosition } from "../shared/geo";
import { Button } from "../ui/Button";
import { StatusLabel } from "../ui/Feedback";
import { kindLabel } from "./RowReviewFormat";

export function Interpreted({ row }: { row: RowDetail }) {
  const i18n = useI18n();
  const { t } = i18n;
  const candidate = (row.interpreted ?? {}) as Record<string, unknown>;
  const position = candidate.position as
    | { latitude: string; longitude: string; latitude_format: string; longitude_format: string }
    | null
    | undefined;
  const count = (name: string) => {
    if (!(name in candidate)) return null;
    const value = candidate[name];
    // Unknown, zero and an error are three different answers.
    if (value === null) return row.error_codes.length ? t("review.unreadable") : t("review.unknown");
    return i18n.number(Number(value));
  };
  const inferred = Boolean(position && `${position.latitude_format}${position.longitude_format}`.includes("inferred"));
  const counts = ["nb_survivor", "female", "under_18", "death_nb_people"].filter((name) => name in candidate);
  return (
    <dl className="review-facts">
      <div>
        <dt>{t("review.field.date")}</dt>
        <dd>{typeof candidate.occurred_on === "string" ? i18n.date(candidate.occurred_on) : t("review.unreadable")}</dd>
      </div>
      <div>
        <dt>{t("review.field.kind")}</dt>
        <dd>{typeof candidate.kind === "string" ? kindLabel(i18n, candidate.kind) : t("review.unreadable")}</dd>
      </div>
      {counts.map((name) => (
        <div key={name}>
          <dt>{t(`review.field.${name}` as Parameters<I18n["t"]>[0])}</dt>
          <dd>{count(name)}</dd>
        </div>
      ))}
      <div>
        <dt>{t("review.field.position")}</dt>
        <dd>
          {position
            ? formatPosition(i18n, Number(position.latitude), Number(position.longitude))
            : t("review.unknown")}
          {inferred && <span className="review-note"> {t("review.inferredHemisphere")}</span>}
        </dd>
      </div>
    </dl>
  );
}

export function Received({ row }: { row: RowDetail }) {
  const { t } = useI18n();
  return (
    <div className="ui-table review-received">
      <table>
        <caption className="sr-only">{t("review.received")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("review.column")}</th>
            <th scope="col">{t("review.value")}</th>
          </tr>
        </thead>
        <tbody>
          {row.received.cells.map((cell, index) => (
            <tr key={index}>
              <th scope="row">{row.received.headers[index] || t("review.unnamedColumn", { index: index + 1 })}</th>
              {/* Raw text exactly as received; React escapes it, nothing is interpreted as HTML. */}
              <td className="review-raw">{cell}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecordedDecision({ row }: { row: RowDetail }) {
  const i18n = useI18n();
  const decision = row.decision;
  if (!decision) return null;
  return (
    <section aria-labelledby="decision-title">
      <h3 id="decision-title">{i18n.t("review.decision.recorded")}</h3>
      <p>
        <StatusLabel status="linked" /> {i18n.t("review.private")}
      </p>
      <dl className="review-facts">
        <div>
          <dt>{i18n.t("review.decision.identity")}</dt>
          <dd className="review-raw">{decision.external_id}</dd>
        </div>
        <div>
          <dt>{i18n.t("review.decision.match")}</dt>
          <dd>{i18n.t(`review.match.${decision.match}` as Parameters<I18n["t"]>[0])}</dd>
        </div>
        <div>
          <dt>{i18n.t("review.decision.by")}</dt>
          <dd>{decision.approved_by}</dd>
        </div>
        <div>
          <dt>{i18n.t("review.decision.reason")}</dt>
          <dd>{decision.reason}</dd>
        </div>
      </dl>
    </section>
  );
}

export function ReportDoubt({ title }: { title: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const link = window.location.href;
  const subject = t("review.report.subject", { title });
  const body = t("review.report.body", { title, link });
  return (
    <div className="review-report">
      <p className="review-note">{t("review.report.help")}</p>
      <div className="review-report__actions">
        <a className="pill-button" href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}>
          {t("review.report.write")}
        </a>
        <Button
          variant="quiet"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(`${subject}\n\n${body}`);
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}
        >
          {t("review.report.copy")}
        </Button>
      </div>
      <p role="status" className="review-note">
        {copied ? t("review.report.copied") : ""}
      </p>
    </div>
  );
}

