import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorCode, fetchClient, uploadBody, type Diagnostic, type Me, type Sheet } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { serverMessageKey } from "../review/RowReview";
import { Link, navigate, withQuery } from "../router";
import { isAbortError, useAbortableRequest } from "../shared/abortable";
import { Button } from "../ui/Button";
import { EmptyState, InlineMessage, PendingState } from "../ui/Feedback";
import { FileInput } from "../ui/FileInput";
import { SelectField } from "../ui/SelectField";
import { ME_QUERY } from "../workspace/WorkspaceShell";
import { DiagnosticSummary } from "./DiagnosticSummary";
import { sheetLabel, type Key } from "./helpers";
import { DIAGNOSTIC_PATH, IMPORTS_PATH, NEW_PATH } from "./paths";

export function NewImport({ me, step }: { me: Me; step: "form" | "diagnostic" }) {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const options = api.useQuery("get", "/api/private/v1/imports/options/", {}, { enabled: me.permissions.stage_snapshot });
  const [source, setSource] = useState("");
  const [sheet, setSheet] = useState<Sheet | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  // The diagnostic and the exact choices it was made for: saving sends those, never newer ones.
  const [result, setResult] = useState<{ diagnostic: Diagnostic; source: string; sheet: Sheet; file: File } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const { run, abort } = useAbortableRequest();
  const alive = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    heading.current?.focus();
  }, [step]);

  if (!me.permissions.stage_snapshot) {
    return <InlineMessage tone="warning">{t("imports.denied")}</InlineMessage>;
  }
  if (options.error) return <InlineMessage tone="error">{t("workspace.loadError")}</InlineMessage>;
  if (!options.data) return <PendingState label={t("workspace.loading")} />;

  const maxBytes = options.data.max_bytes;
  const fileError = !file
    ? submitted
      ? t("imports.error.file")
      : null
    : file.size > maxBytes
      ? t("imports.error.tooLarge", { size: i18n.number(Math.round(maxBytes / 1024 / 1024)) })
      : null;

  const check = async () => {
    setSubmitted(true);
    setFailure(null);
    if (!source || !sheet || !file || file.size > maxBytes) return;
    setChecking(true);
    try {
      // A diagnostic writes nothing: a superseded or abandoned one is simply aborted.
      const { data, error } = await run((signal) =>
        fetchClient.POST("/api/private/v1/imports/diagnose/", { body: uploadBody({ source, sheet, file }), signal }),
      );
      if (error) throw error;
      setResult({ diagnostic: data, source, sheet, file });
      navigate(DIAGNOSTIC_PATH);
    } catch (error) {
      if (!isAbortError(error)) setFailure(t(failureKey(errorCode(error))));
      if (errorCode(error) === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ME_QUERY });
    } finally {
      setChecking(false);
    }
  };

  const save = async () => {
    if (!result) return;
    setSaving(true);
    setFailure(null);
    try {
      // A write is never aborted; if the screen moved on, its result is ignored.
      const { data, error } = await fetchClient.POST("/api/private/v1/imports/", {
        body: uploadBody({ source: result.source, sheet: result.sheet, file: result.file }),
      });
      if (error) throw error;
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/imports/"] });
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/snapshots/"] });
      if (!alive.current) return;
      navigate(withQuery(`${IMPORTS_PATH}/${data.snapshot.id}`, { saved: data.created ? "new" : "existing" }));
    } catch (error) {
      if (!alive.current) return;
      setFailure(t(failureKey(errorCode(error))));
      if (errorCode(error) === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ME_QUERY });
    } finally {
      if (alive.current) setSaving(false);
    }
  };

  if (step === "diagnostic") {
    if (!result) {
      return (
        <>
          <h1 ref={heading} tabIndex={-1}>
            {t("imports.check.title")}
          </h1>
          <EmptyState title={t("imports.check.lost")} action={<Link to={NEW_PATH}>{t("imports.check.chooseAgain")}</Link>}>
            <p>{t("imports.check.lostBody")}</p>
          </EmptyState>
        </>
      );
    }
    return (
      <>
        <h1 ref={heading} tabIndex={-1}>
          {t("imports.check.title")}
        </h1>
        <p className="workspace-lead">
          {t("imports.check.lead", {
            sheet: sheetLabel(i18n, result.diagnostic.sheet),
            file: result.file.name,
            source: result.diagnostic.source.name,
          })}
        </p>
        {failure && <InlineMessage tone="error">{failure}</InlineMessage>}
        <DiagnosticSummary result={result.diagnostic} />
        <section className="workspace-panel" aria-labelledby="next-step">
          <h2 id="next-step">{t("imports.next.title")}</h2>
          {result.diagnostic.existing_snapshot ? (
            <InlineMessage tone="info">
              {t("imports.next.existing")} <Link to={`${IMPORTS_PATH}/${result.diagnostic.existing_snapshot}`}>{t("imports.next.open")}</Link>
            </InlineMessage>
          ) : result.diagnostic.stageable ? (
            <>
              <p>{t("imports.next.saveBody")}</p>
              {result.diagnostic.counts.rows_with_errors > 0 && (
                <p className="review-note">{t("imports.next.blockedRows", { count: result.diagnostic.counts.rows_with_errors })}</p>
              )}
              <div className="workspace-actions">
                <Button variant="primary" loading={saving} onClick={() => void save()}>
                  {t("imports.next.save")}
                </Button>
                <Link to={NEW_PATH}>{t("imports.next.otherFile")}</Link>
              </div>
            </>
          ) : (
            <>
              <InlineMessage tone="error">
                {t(`imports.blocking.${result.diagnostic.blocking_reason ?? "file_errors"}` as Key)}
              </InlineMessage>
              <p>{t("imports.next.fixSource")}</p>
              <Link to={NEW_PATH}>{t("imports.next.otherFile")}</Link>
            </>
          )}
        </section>
      </>
    );
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        {t("imports.new.title")}
      </h1>
      <p className="workspace-lead">{t("imports.new.lead")}</p>
      <form
        className="review-form workspace-panel"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void check();
        }}
      >
        {failure && <InlineMessage tone="error">{failure}</InlineMessage>}
        <SelectField<string>
          label={t("imports.new.source")}
          value={source}
          emptyLabel={t("imports.new.choose")}
          options={options.data.sources.map((item) => ({
            value: item.id,
            label: item.synthetic ? t("imports.new.synthetic", { name: item.name }) : item.name,
          }))}
          onValueChange={(value) => {
            abort();
            setResult(null);
            setSource(value);
          }}
        />
        {submitted && !source && <p className="ui-field__error">{t("imports.error.source")}</p>}
        <SelectField<Sheet>
          label={t("imports.new.sheet")}
          value={sheet}
          emptyLabel={t("imports.new.choose")}
          options={options.data.sheets.map((value) => ({ value, label: sheetLabel(i18n, value) }))}
          onValueChange={(value) => {
            abort();
            setResult(null);
            setSheet(value);
          }}
        />
        {submitted && !sheet && <p className="ui-field__error">{t("imports.error.sheet")}</p>}
        <FileInput
          label={t("imports.new.file")}
          description={t("imports.new.fileHelp", { size: i18n.number(Math.round(maxBytes / 1024 / 1024)) })}
          accept=".csv,text/csv"
          file={file}
          onFileChange={(next) => {
            abort();
            setFile(next);
            setResult(null);
          }}
          error={fileError}
        />
        <p className="review-note">{t("imports.new.private")}</p>
        <div className="workspace-actions">
          <Button type="submit" variant="primary" loading={checking}>
            {t("imports.new.check")}
          </Button>
          <Link to={IMPORTS_PATH}>{t("ui.cancel")}</Link>
        </div>
      </form>
    </>
  );
}

function failureKey(code: string): Key {
  if (code === "throttled") return "imports.error.throttled";
  if (code === "invalid") return "imports.error.invalid";
  if (code === "permission_denied") return "imports.denied";
  if (code === "http_413") return "imports.error.tooLargeServer";
  return serverMessageKey(code);
}

