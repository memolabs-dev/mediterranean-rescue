import { useState } from "react";
import type { Kind } from "../api/client";
import { kinds } from "../filters";
import { LOCALES } from "../i18n/format";
import { useI18n } from "../i18n/I18nProvider";
import { useDevText } from "./messages";
import { Button } from "../ui/Button";
import { Checkbox } from "../ui/Checkbox";
import { ChoiceGroup } from "../ui/ChoiceGroup";
import { ConfirmationDialog } from "../ui/ConfirmationDialog";
import { DateRange } from "../ui/DateRange";
import { Dialog } from "../ui/Dialog";
import { Disclosure } from "../ui/Disclosure";
import { EmptyState, ErrorSummary, InlineMessage, PendingState, StatusLabel, type Status } from "../ui/Feedback";
import { Pagination } from "../ui/Pagination";
import { SelectField } from "../ui/SelectField";
import { Tabs } from "../ui/Tabs";
import { TextField } from "../ui/TextField";

const STATUSES: readonly Status[] = ["blocked", "needsReview", "linked", "draft", "published", "withdrawn", "unknown", "training"];
type Decision = "create" | "link" | "later";

// Internal development page listing the reusable components with their states (ADR 0008).
export default function Catalog() {
  const { t, locale, setLocale } = useI18n();
  const d = useDevText();
  const [reason, setReason] = useState("");
  // Errors appear after the field is left or the form submitted, not on arrival (TextField contract).
  const [reasonTouched, setReasonTouched] = useState(false);
  const [kind, setKind] = useState<Kind | "">("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [include, setInclude] = useState(false);
  const [offset, setOffset] = useState(0);
  const [range, setRange] = useState({ start: "", end: "" });
  // The summary takes focus when shown, as after a failed submission: show it on demand.
  const [submission, setSubmission] = useState(0);

  return (
    <main className="catalog">
      <div className="catalog__header">
        <h1>{d("title")}</h1>
        <div className="catalog__row">
          {LOCALES.map((value) => (
            <Button key={value} size="sm" variant={value === locale ? "primary" : "secondary"} onClick={() => setLocale(value)}>
              {value.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>
      <InlineMessage tone="info">{d("notice")}</InlineMessage>

      <section>
        <h2>{d("buttons")}</h2>
        <div className="catalog__row">
          <Button variant="primary">{d("primary")}</Button>
          <Button variant="secondary">{d("secondary")}</Button>
          <Button variant="quiet">{d("quiet")}</Button>
          <Button variant="danger">{d("danger")}</Button>
          <Button disabled>{d("disabled")}</Button>
          <Button variant="primary" loading>
            {d("loading")}
          </Button>
          <Button size="sm">{d("secondary")}</Button>
          <Button size="lg" variant="primary">
            {d("primary")}
          </Button>
        </div>
      </section>

      <section>
        <h2>{d("fields")}</h2>
        <div className="catalog__grid">
          <TextField
            id="catalog-reason"
            label={d("reason")}
            description={d("reasonHelp")}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            onBlur={() => setReasonTouched(true)}
            error={reasonTouched && !reason.trim() ? d("reasonError") : null}
          />
          <TextField id="catalog-port" label={d("port")} optional defaultValue="Pozzallo" />
          <SelectField<Kind>
            label={d("kind")}
            value={kind}
            emptyLabel={t("filters.allKinds")}
            options={kinds.map((value) => ({ value, label: t(`kind.${value}`) }))}
            onValueChange={setKind}
          />
        </div>
      </section>

      <section>
        <h2>{d("choices")}</h2>
        <ChoiceGroup<Decision>
          legend={d("decision")}
          value={decision}
          onValueChange={setDecision}
          choices={[
            { value: "create", label: d("decision.create") },
            { value: "link", label: d("decision.link") },
            { value: "later", label: d("decision.later") },
          ]}
        />
        <Checkbox label={d("include")} checked={include} onCheckedChange={setInclude} />
        <Checkbox label={d("include")} checked={false} indeterminate onCheckedChange={() => {}} />
      </section>

      <section>
        <h2>{d("overlays")}</h2>
        <div className="catalog__row">
          <Dialog title={d("dialog.title")} trigger={<Button>{d("dialog.open")}</Button>}>
            <p>{d("dialog.body")}</p>
          </Dialog>
          <ConfirmationDialog
            danger
            trigger={<Button variant="danger">{d("confirm.open")}</Button>}
            title={d("confirm.title")}
            consequence={d("confirm.body")}
            confirmLabel={d("confirm.action")}
            onConfirm={() => new Promise((resolve) => setTimeout(resolve, 800))}
            failureMessage={() => d("message.error")}
          />
        </div>
      </section>

      <section>
        <h2>{d("disclosure")}</h2>
        <Tabs
          label={d("disclosure")}
          defaultValue="summary"
          items={[
            { value: "summary", label: d("tabs.summary"), content: <p>{d("tabs.summaryBody")}</p> },
            { value: "source", label: d("tabs.source"), content: <p>{d("tabs.sourceBody")}</p> },
          ]}
        />
        <Disclosure title={d("disclosure.title")}>
          <p>{d("disclosure.body")}</p>
        </Disclosure>
      </section>

      <section>
        <h2>{d("feedback")}</h2>
        <div className="catalog__row">
          {STATUSES.map((status) => (
            <StatusLabel key={status} status={status} />
          ))}
        </div>
        <InlineMessage tone="info">{d("message.info")}</InlineMessage>
        <InlineMessage tone="success">{d("message.success")}</InlineMessage>
        <InlineMessage tone="warning">{d("message.warning")}</InlineMessage>
        <InlineMessage tone="error">{d("message.error")}</InlineMessage>
        <Button
          onClick={() => {
            setReasonTouched(true);
            setSubmission((count) => count + 1);
          }}
        >
          {d("errorSummary.show")}
        </Button>
        {submission > 0 && (
          <ErrorSummary
            submission={submission}
            errors={[
              ...(reason.trim() ? [] : [{ fieldId: "catalog-reason", message: d("errorSummary.reason") }]),
              { fieldId: "catalog-port", message: d("errorSummary.port") },
            ]}
          />
        )}
        <EmptyState title={d("empty.title")}>
          <p>{d("empty.body")}</p>
        </EmptyState>
        <PendingState label={d("pending")} />
      </section>

      <section>
        <h2>{d("navigation")}</h2>
        <Pagination offset={offset} limit={25} total={370} hasNext={offset + 25 < 370} onOffsetChange={setOffset} />
        <DateRange
          legend={d("period")}
          startLabel={t("filters.from")}
          endLabel={t("filters.to")}
          start={range.start}
          end={range.end}
          onApply={(start, end) => setRange({ start, end })}
        />
      </section>
    </main>
  );
}
