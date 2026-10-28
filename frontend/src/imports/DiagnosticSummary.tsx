import type { Diagnostic } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { issueText, type Key } from "./helpers";

export function DiagnosticSummary({ result }: { result: Diagnostic }) {
  const i18n = useI18n();
  const { t } = i18n;
  const counts = result.counts;
  const readKey = `imports.read.${result.source_read}` as Key;
  const read = t(readKey);
  return (
    <>
      <section className="workspace-panel" aria-labelledby="reading">
        <h2 id="reading">{t("imports.check.reading")}</h2>
        <p>{read === readKey ? result.source_read : read}</p>
        <dl className="workspace-facts">
          <div>
            <dt>{t("imports.count.rows")}</dt>
            <dd>{i18n.number(counts.rows_diagnosed)}</dd>
          </div>
          <div>
            <dt>{t("imports.count.rowsWithErrors")}</dt>
            <dd>{i18n.number(counts.rows_with_errors)}</dd>
          </div>
          <div>
            <dt>{t("imports.count.rowsWithWarnings")}</dt>
            <dd>{i18n.number(counts.rows_with_warnings)}</dd>
          </div>
          <div>
            <dt>{t("imports.count.blank")}</dt>
            <dd>{i18n.number(counts.blank_rows_skipped)}</dd>
          </div>
        </dl>
      </section>
      {result.issues_by_code.length > 0 && (
        <section className="workspace-panel" aria-labelledby="problems">
          <h2 id="problems">{t("imports.check.problems")}</h2>
          <p className="review-note">{t("imports.check.problemsHelp")}</p>
          <ul className="workspace-issues">
            {result.issues_by_code.map((item) => (
              <li key={`${item.code}-${item.severity}`}>
                <span className={`workspace-severity workspace-severity--${item.severity}`}>
                  {t(item.severity === "error" ? "imports.severity.error" : "imports.severity.warning")}
                </span>{" "}
                {issueText(i18n, item.code)} <span className="review-note">({t("imports.check.times", { count: item.count })})</span>
              </li>
            ))}
          </ul>
          <details className="workspace-details">
            <summary>{t("imports.check.where")}</summary>
            <ul className="workspace-locations">
              {result.issues.map((issue, index) => (
                <li key={index}>
                  {issue.line ? t("imports.check.line", { line: issue.line }) : t("imports.check.wholeFile")}
                  {issue.field ? ` · ${issue.field}` : ""} : {issueText(i18n, issue.code)}
                </li>
              ))}
            </ul>
            {result.issues_truncated && <p className="review-note">{t("imports.check.truncated", { count: result.issues.length })}</p>}
          </details>
        </section>
      )}
    </>
  );
}

