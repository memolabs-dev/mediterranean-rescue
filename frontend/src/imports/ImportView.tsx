import { api, errorCode, type ImportDetail, type Me } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Link, useLocation, withQuery } from "../router";
import { InlineMessage, PendingState } from "../ui/Feedback";
import { issueText, localDay, sheetLabel } from "./helpers";
import { IMPORTS_PATH, REVIEW_SHEETS } from "./paths";

export function ImportView({ id, me }: { id: string; me: Me }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { query } = useLocation();
  const detail = api.useQuery("get", "/api/private/v1/imports/{id}/", { params: { path: { id } } });
  const saved = query.get("saved");
  if (detail.error) {
    return (
      <InlineMessage tone="error">
        {errorCode(detail.error) === "not_found" ? t("imports.missing") : t("workspace.loadError")}
      </InlineMessage>
    );
  }
  if (!detail.data) return <PendingState label={t("workspace.loading")} />;
  const data: ImportDetail = detail.data;
  return (
    <>
      <p>
        <Link to={IMPORTS_PATH}>{t("imports.back")}</Link>
      </p>
      <h1>{t("imports.detail.title", { sheet: sheetLabel(i18n, data.sheet), date: i18n.date(localDay(data.created_at)) })}</h1>
      {saved === "new" && <InlineMessage tone="success">{t("imports.detail.saved")}</InlineMessage>}
      {saved === "existing" && <InlineMessage tone="info">{t("imports.detail.alreadySaved")}</InlineMessage>}
      <p className="workspace-lead">{t("imports.detail.private")}</p>
      <dl className="workspace-facts workspace-panel">
        <div>
          <dt>{t("imports.col.source")}</dt>
          <dd>{data.source.name}</dd>
        </div>
        <div>
          <dt>{t("imports.col.by")}</dt>
          <dd>{data.staged_by}</dd>
        </div>
        <div>
          <dt>{t("imports.count.rows")}</dt>
          <dd>{i18n.number(data.row_count)}</dd>
        </div>
        <div>
          <dt>{t("imports.count.rowsWithErrors")}</dt>
          <dd>{i18n.number(data.rows_with_errors)}</dd>
        </div>
      </dl>
      {data.errors_by_code.length > 0 && (
        <section className="workspace-panel" aria-labelledby="detail-problems">
          <h2 id="detail-problems">{t("imports.detail.problems")}</h2>
          <ul className="workspace-issues">
            {data.errors_by_code.map((item) => (
              <li key={item.code}>
                {issueText(i18n, item.code)} <span className="review-note">({t("imports.detail.rows", { count: item.rows })})</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="workspace-panel" aria-labelledby="detail-next">
        <h2 id="detail-next">{t("imports.next.title")}</h2>
        {data.review && REVIEW_SHEETS.includes(data.sheet) ? (
          <>
            <p>{t("imports.detail.reviewCounts", { toReview: data.review.to_review, blocked: data.review.blocked, linked: data.review.linked })}</p>
            {me.permissions.review_identity ? (
              <Link to={withQuery("/workspace/review", { snapshot: data.id })}>{t("imports.detail.openReview")}</Link>
            ) : (
              <p className="review-note">{t("imports.detail.othersReview")}</p>
            )}
          </>
        ) : (
          <>
            <p>{t("imports.detail.portsNext")}</p>
            {me.permissions.review_identity ? (
              <Link to="/workspace/ports">{t("imports.detail.openPorts")}</Link>
            ) : (
              <p className="review-note">{t("imports.detail.othersReview")}</p>
            )}
          </>
        )}
      </section>
    </>
  );
}
