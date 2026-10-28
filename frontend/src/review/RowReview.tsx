import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorCode, fetchClient, type IdentityCandidate } from "../api/client";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { setNavigationGuard } from "../router";
import { Button } from "../ui/Button";
import { EvidenceBlock } from "../explore/Evidence";
import { ChoiceGroup } from "../ui/ChoiceGroup";
import { Disclosure } from "../ui/Disclosure";
import { ErrorSummary, InlineMessage, PendingState, StatusLabel, type SummaryError } from "../ui/Feedback";
import { SearchCombobox } from "../ui/SearchCombobox";
import { TextField } from "../ui/TextField";
import { AccessProblem } from "./AccessProblem";
import { Interpreted, Received, RecordedDecision, ReportDoubt } from "./RowDetails";
import { codeText, identityLabel, rowTitle, serverMessageKey, sheetName } from "./RowReviewFormat";

export { codeText, countLabel, identityLabel, kindLabel, serverMessageKey } from "./RowReviewFormat";
export type { Summary } from "./RowReviewFormat";

type Decision = "create" | "link" | "later";

export interface RowReviewProps {
  rowId: string;
  snapshotId: string;
  /** Called after the server confirmed the decision; `next` asks to open the following row. */
  onDecided: (next: boolean) => void;
  onClose: () => void;
}

export function RowReview({ rowId, snapshotId, onDecided, onClose }: RowReviewProps) {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const rowQuery = api.useQuery("get", "/api/private/v1/review/rows/{id}/", { params: { path: { id: rowId } } });
  const decide = api.useMutation("post", "/api/private/v1/review/rows/{id}/decision/");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [candidate, setCandidate] = useState<string | null>(null);
  const [searched, setSearched] = useState<IdentityCandidate | null>(null);
  const [reason, setReason] = useState("");
  const [submission, setSubmission] = useState(0);
  const [outcome, setOutcome] = useState<"saved" | "later" | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  // Writes are not aborted (their outcome would be unknown); a late result for a row the user
  // has left is ignored instead.
  const alive = useRef(true);
  useEffect(() => {
    // Set again on every mount: React's development double mount runs the cleanup once, and a
    // flag left false would silently drop every answer (acceptance of 24 October 2026, D1).
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // Leaving with a typed reason that was not submitted loses it: ask first, in the app and in
  // the browser.
  const dirty = reason.trim() !== "" && !decide.isSuccess;
  const unsavedQuestion = t("review.unsaved");
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    setNavigationGuard(() => window.confirm(unsavedQuestion));
    return () => {
      window.removeEventListener("beforeunload", warn);
      setNavigationGuard(null);
    };
  }, [dirty, unsavedQuestion]);

  // Opening a row (or recording its decision) moves focus to its title.
  const loaded = rowQuery.isSuccess;
  useEffect(() => {
    if (loaded) heading.current?.focus();
  }, [loaded, outcome]);

  if (rowQuery.isPending) return <PendingState label={t("review.loadingRow")} />;
  if (rowQuery.error) {
    const code = errorCode(rowQuery.error);
    if (code === "not_authenticated" || code === "permission_denied") return <AccessProblem code={code} />;
    return (
      <InlineMessage tone="error">
        {t(code === "not_found" ? "review.rowMissing" : "review.loadError")}{" "}
        <Button size="sm" onClick={() => void rowQuery.refetch()}>
          {t("ui.retry")}
        </Button>
      </InlineMessage>
    );
  }
  const row = rowQuery.data;
  const chosenIdentity = decision === "link" ? (searched?.id ?? candidate) : null;
  const errors: SummaryError[] = [];
  if (decision === null) errors.push({ fieldId: "review-decision", message: t("review.error.decision") });
  if (decision === "link" && !chosenIdentity)
    errors.push({ fieldId: "review-identity", message: t("review.error.identity") });
  if (decision !== "later" && !reason.trim()) errors.push({ fieldId: "review-reason", message: t("review.error.reason") });

  const submit = async (next: boolean) => {
    setSubmission((count) => count + 1);
    setServerError(null);
    if (errors.length) return;
    if (decision === "later") {
      // Nothing is created or counted as a validation.
      setOutcome("later");
      onClose();
      return;
    }
    try {
      await decide.mutateAsync({
        params: { path: { id: rowId } },
        body:
          decision === "create"
            ? { action: "create_identity", reason }
            : { action: "link", identity: chosenIdentity ?? "", reason },
      });
      // Only a saved decision lifts the guard: after a failure the typed reason stays protected.
      setNavigationGuard(null);
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/review/rows/"] });
      if (!alive.current) return;
      setOutcome("saved");
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/review/rows/{id}/"] });
      if (alive.current) onDecided(next);
    } catch (error) {
      if (!alive.current) return;
      const code = errorCode(error);
      setServerError(code);
      // An expired session shows the sign-in screen; a conflict or an unknown outcome is read again.
      if (code === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/me/"] });
      if (code === "conflict" || code === "network") void rowQuery.refetch();
    }
  };

  // A row rebuilt from the public logbook is verified against its sentence (ADR 0014).
  const fromLogbook = row.evidence !== null;
  const verb =
    decision === "link" ? t("review.action.link") : t(fromLogbook ? "review.action.verifyLogbook" : "review.action.create");
  const status = row.status === "to_review" ? "needsReview" : row.status === "blocked" ? "blocked" : "linked";

  return (
    <article className="review-row" aria-labelledby="review-row-title">
      <div className="review-row__header">
        <h2 id="review-row-title" ref={heading} tabIndex={-1}>
          {rowTitle(i18n, row.interpreted)}
        </h2>
        <StatusLabel status={status} />
        <Button size="sm" variant="quiet" onClick={onClose}>
          {t("ui.close")}
        </Button>
      </div>
      {row.evidence ? (
        <>
          <p className="review-note">{t("review.provenanceLogbook")}</p>
          <EvidenceBlock evidence={row.evidence} />
          <section aria-labelledby="compare-title" className="review-compare">
            <h3 id="compare-title">{t("review.compare.title")}</h3>
            <ul>
              <li>{t("review.compare.date")}</li>
              <li>{t("review.compare.people")}</li>
              <li>{t("review.compare.place")}</li>
            </ul>
            <p className="review-note">{t("review.compare.wrong")}</p>
          </section>
        </>
      ) : (
        <p className="review-note">{t("review.provenance", { sheet: sheetName(i18n, row.snapshot.sheet), line: row.line })}</p>
      )}

      {outcome === "saved" && row.status === "linked" && (
        <InlineMessage tone="success">{t("review.saved")}</InlineMessage>
      )}
      {/* Outside the form: after a conflict the row may be linked and the form gone. */}
      {serverError && <InlineMessage tone="error">{t(serverMessageKey(serverError))}</InlineMessage>}

      {fromLogbook && (row.interpreted as { kind?: string } | null)?.kind === "medevac" ? (
        // A medical evacuation is never exported to the sheet: no columns to show.
        <p className="review-note">{t("review.notForSheet")}</p>
      ) : fromLogbook ? (
        // The sheet's columns matter to whoever pastes the row; the sentence is what a volunteer reads.
        <Disclosure title={t("review.sheetColumns")}>
          <Received row={row} />
        </Disclosure>
      ) : (
        <section aria-labelledby="received-title">
          <h3 id="received-title">{t("review.received")}</h3>
          <Received row={row} />
        </section>
      )}
      <section aria-labelledby="interpreted-title">
        <h3 id="interpreted-title">{t("review.interpreted")}</h3>
        {row.proposal.kind === "repeat" && (
          <InlineMessage tone="warning">{t("review.repeat", { line: row.proposal.repeats_line ?? "?" })}</InlineMessage>
        )}
        {row.error_codes.length > 0 && (
          <InlineMessage tone="error">
            {t("review.blocked")} {row.error_codes.map((code) => codeText(i18n, code)).join(" ")}
          </InlineMessage>
        )}
        <Interpreted row={row} />
      </section>

      {row.status === "linked" && <RecordedDecision row={row} />}

      {row.status === "to_review" && (
        <section aria-labelledby="match-title">
          <h3 id="match-title">{t("review.suggested")}</h3>
          <p>{t(`review.proposal.${row.proposal.kind}` as Parameters<I18n["t"]>[0])}</p>
          {/* Decisions are irreversible: only the buttons submit. Enter in a field (the identity
              search above all) must never record a decision. */}
          <form className="review-form" noValidate onSubmit={(event) => event.preventDefault()}>
            {submission > 0 && errors.length > 0 && <ErrorSummary errors={errors} submission={submission} />}
            <div id="review-decision">
              <ChoiceGroup<Decision>
                legend={t("review.decisionLegend")}
                value={decision}
                onValueChange={setDecision}
                choices={[
                  { value: "create", label: t("review.choice.create") },
                  { value: "link", label: t("review.choice.link"), description: t("review.choice.linkHelp") },
                  { value: "later", label: t("review.choice.later"), description: t("review.choice.laterHelp") },
                ]}
              />
            </div>
            {decision === "link" && (
              <div id="review-identity" className="review-identity">
                {row.proposal.candidates.length > 0 && (
                  <ChoiceGroup<string>
                    legend={t("review.candidates")}
                    value={searched ? null : candidate}
                    onValueChange={(value) => {
                      setCandidate(value);
                      setSearched(null);
                    }}
                    choices={row.proposal.candidates.map((item) => ({ value: item.id, label: identityLabel(i18n, item) }))}
                  />
                )}
                <SearchCombobox<IdentityCandidate>
                  label={t("review.searchIdentity")}
                  placeholder={t("review.searchPlaceholder")}
                  value={searched}
                  onValueChange={(value) => {
                    setSearched(value);
                    if (value) setCandidate(null);
                  }}
                  itemId={(item) => item.id}
                  itemLabel={(item) => identityLabel(i18n, item)}
                  search={async (q, signal) => {
                    const { data, error } = await fetchClient.GET("/api/private/v1/review/identities/", {
                      params: { query: { snapshot: snapshotId, q } },
                      signal,
                    });
                    if (error) throw new Error(errorCode(error));
                    return data.items;
                  }}
                />
              </div>
            )}
            {decision !== "later" && (
              <TextField
                id="review-reason"
                label={t("review.reason")}
                description={t("review.reasonHelp")}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                error={submission > 0 && !reason.trim() ? t("review.error.reason") : null}
              />
            )}
            <p className="review-note">{t("review.effect")}</p>
            <ReportDoubt title={rowTitle(i18n, row.interpreted)} />
            <div className="review-actions">
              <Button variant="primary" loading={decide.isPending} onClick={() => void submit(false)}>
                {decision === "later" ? t("review.action.later") : verb}
              </Button>
              {decision !== "later" && (
                <Button loading={decide.isPending} onClick={() => void submit(true)}>
                  {t("review.action.andNext", { action: verb })}
                </Button>
              )}
            </div>
          </form>
        </section>
      )}
    </article>
  );
}

