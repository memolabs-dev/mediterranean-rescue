import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorCode, fetchClient, type PortInterpretation, type PortLabelDetail, type PortRef } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { serverMessageKey } from "../review/RowReview";
import { setNavigationGuard } from "../router";
import { Button } from "../ui/Button";
import { ChoiceGroup } from "../ui/ChoiceGroup";
import { ErrorSummary, InlineMessage, PendingState, type SummaryError } from "../ui/Feedback";
import { SelectField } from "../ui/SelectField";
import { TextField } from "../ui/TextField";
import { ME_QUERY } from "../workspace/WorkspaceShell";
import { coordinates, parseDecimal, portName, readingText } from "./portFormat";
import { PortSearch } from "./PortSearch";

type PortChoice = "existing" | "from_list" | "enter";

export function LabelReading({ id, onClose, onNext }: { id: string; onClose: () => void; onNext: () => void }) {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const detail = api.useQuery("get", "/api/private/v1/ports/labels/{id}/", { params: { path: { id } } });
  const vessels = api.useQuery("get", "/api/private/v1/vessels/", {});
  const [interpretation, setInterpretation] = useState<PortInterpretation | null>(null);
  const [portChoice, setPortChoice] = useState<PortChoice | null>(null);
  const [existing, setExisting] = useState<PortRef | null>(null);
  const [several, setSeveral] = useState<PortRef[]>([]);
  const [vessel, setVessel] = useState("");
  const [longitude, setLongitude] = useState("");
  const [latitude, setLatitude] = useState("");
  const [country, setCountry] = useState("");
  const [reason, setReason] = useState("");
  const [submission, setSubmission] = useState(0);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const alive = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    if (detail.data) heading.current?.focus();
  }, [detail.data, saved]);
  // Any choice or typed value counts as unsaved input, until a reading is recorded.
  const dirty =
    !saved &&
    !detail.data?.reading &&
    Boolean(interpretation || reason.trim() || latitude || longitude || country || vessel || several.length);
  useEffect(() => {
    setNavigationGuard(dirty ? () => window.confirm(t("ports.unsaved")) : null);
    return () => setNavigationGuard(null);
  }, [dirty, t]);

  if (detail.error) {
    return (
      <InlineMessage tone="error">
        {errorCode(detail.error) === "not_found" ? t("ports.missing") : t("workspace.loadError")}
      </InlineMessage>
    );
  }
  if (!detail.data) return <PendingState label={t("workspace.loading")} />;
  const data: PortLabelDetail = detail.data;
  const row = data.port_list_row;
  const listPosition = row && row.position && row.error_codes.length === 0 ? row.position : null;
  const availableVessels = vessels.data?.items ?? [];

  const lon = parseDecimal(longitude);
  const lat = parseDecimal(latitude);
  const errors: SummaryError[] = [];
  if (!interpretation) errors.push({ fieldId: "port-interpretation", message: t("ports.error.interpretation") });
  if (interpretation === "port") {
    if (!portChoice) errors.push({ fieldId: "port-choice", message: t("ports.error.choice") });
    if (portChoice === "existing" && !existing) errors.push({ fieldId: "port-existing", message: t("ports.error.existing") });
    if (portChoice === "enter") {
      if (lat === null || lat < -90 || lat > 90) errors.push({ fieldId: "port-latitude", message: t("ports.error.latitude") });
      if (lon === null || lon < -180 || lon > 180) errors.push({ fieldId: "port-longitude", message: t("ports.error.longitude") });
      if (lat === 0 && lon === 0) errors.push({ fieldId: "port-latitude", message: t("ports.error.zero") });
    }
    if (country && !/^[A-Za-z]{2}$/.test(country)) errors.push({ fieldId: "port-country", message: t("ports.error.country") });
  }
  if (interpretation === "ports" && several.length < 2) errors.push({ fieldId: "port-several", message: t("ports.error.several") });
  if (interpretation === "vessel" && !vessel) errors.push({ fieldId: "port-vessel", message: t("ports.error.vessel") });
  if (!reason.trim()) errors.push({ fieldId: "port-reason", message: t("ports.error.reason") });
  const shown = submission > 0 ? errors : [];
  const errorFor = (fieldId: string) => shown.find((error) => error.fieldId === fieldId)?.message ?? null;

  const submit = async (andNext: boolean) => {
    setSubmission((value) => value + 1);
    setServerError(null);
    if (errors.length > 0 || !interpretation) return;
    const body =
      interpretation === "port"
        ? portChoice === "existing" && existing
          ? { interpretation, ports: [existing.id], reason }
          : {
              interpretation,
              new_port: {
                // An entered position still records which port-list row the port comes from.
                from_port_list: portChoice === "from_list" || (portChoice === "enter" && Boolean(row)),
                ...(portChoice === "enter" && lon !== null && lat !== null ? { longitude: lon, latitude: lat } : {}),
                country_code: country.trim().toUpperCase(),
              },
              reason,
            }
        : interpretation === "ports"
          ? { interpretation, ports: several.map((port) => port.id), reason }
          : interpretation === "vessel"
            ? { interpretation, vessel, reason }
            : { interpretation, reason };
    setSaving(true);
    try {
      // A write is never aborted; a result arriving after the user left is ignored.
      const { data: updated, error } = await fetchClient.POST("/api/private/v1/ports/labels/{id}/decision/", {
        params: { path: { id } },
        body,
      });
      if (error) throw error;
      // The answer is the label as now recorded: shown at once, and the list is read again.
      queryClient.setQueryData(api.queryOptions("get", "/api/private/v1/ports/labels/{id}/", { params: { path: { id } } }).queryKey, updated);
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/ports/labels/"] });
      if (!alive.current) return;
      setSaved(true);
      setNavigationGuard(null);
      if (andNext) onNext();
    } catch (error) {
      if (!alive.current) return;
      const code = errorCode(error);
      setServerError(t(code === "permission_denied" ? "ports.denied" : serverMessageKey(code)));
      if (code === "conflict") void detail.refetch();
      if (code === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ME_QUERY });
    } finally {
      if (alive.current) setSaving(false);
    }
  };

  return (
    <article className="review-row" aria-labelledby="label-title">
      <div className="review-row__header">
        <h2 id="label-title" ref={heading} tabIndex={-1}>
          “{data.label}”
        </h2>
        <Button size="sm" variant="quiet" onClick={onClose}>
          {t("ui.close")}
        </Button>
      </div>
      <p className="review-note">{t("ports.detail.source", { name: data.source.name })}</p>
      {serverError && <InlineMessage tone="error">{serverError}</InlineMessage>}

      <section aria-labelledby="label-where">
        <h3 id="label-where">{t("ports.detail.where")}</h3>
        <p>
          {data.operations > 0
            ? t("ports.detail.operations", { count: data.operations })
            : t("ports.detail.noOperations")}
        </p>
        {data.operation_lines.length > 0 && (
          <ul className="workspace-locations">
            {data.operation_lines.map((line) => (
              <li key={line.line}>
                {t("ports.detail.operationLine", {
                  line: line.line,
                  date: line.occurred_on ? i18n.date(line.occurred_on) : t("review.unknown"),
                })}
              </li>
            ))}
          </ul>
        )}
        {!row ? (
          <p>{t("ports.detail.notInList")}</p>
        ) : listPosition ? (
          <p>{t("ports.detail.inList", { line: row.line, position: coordinates(i18n, listPosition) })}</p>
        ) : (
          <>
            <InlineMessage tone="warning">{t("ports.detail.unclear", { line: row.line })}</InlineMessage>
            {data.port_list_cells && (
              <table className="review-table">
                <caption className="sr-only">{t("ports.detail.cells")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("review.column")}</th>
                    <th scope="col">{t("review.value")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.port_list_cells.cells.map((cell, index) => (
                    <tr key={index}>
                      <th scope="row">{data.port_list_cells?.headers[index] || t("review.unnamedColumn", { index: index + 1 })}</th>
                      <td>{cell}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </section>

      {data.reading ? (
        <section aria-labelledby="label-reading">
          <h3 id="label-reading">{t("ports.detail.recorded")}</h3>
          {saved && <InlineMessage tone="success">{t("ports.saved")}</InlineMessage>}
          <p>{readingText(i18n, data)}</p>
          <dl className="workspace-facts">
            <div>
              <dt>{t("review.decision.by")}</dt>
              <dd>{data.reading.approved_by}</dd>
            </div>
            <div>
              <dt>{t("review.decision.reason")}</dt>
              <dd>{data.reading.reason}</dd>
            </div>
          </dl>
          <div className="workspace-actions">
            <Button variant="primary" onClick={onNext}>
              {t("ports.next")}
            </Button>
          </div>
        </section>
      ) : (
        <form className="review-form" noValidate onSubmit={(event) => event.preventDefault()}>
          <ErrorSummary errors={shown} submission={submission} />
          <div id="port-interpretation" tabIndex={-1}>
            <ChoiceGroup<PortInterpretation>
              legend={t("ports.question")}
              value={interpretation}
              onValueChange={setInterpretation}
              choices={[
                { value: "port", label: t("ports.choice.port"), description: t("ports.choice.portHelp") },
                { value: "ports", label: t("ports.choice.ports"), description: t("ports.choice.portsHelp") },
                {
                  value: "vessel",
                  label: t("ports.choice.vessel"),
                  description: availableVessels.length ? t("ports.choice.vesselHelp") : t("ports.choice.vesselNone"),
                },
                { value: "not_a_port", label: t("ports.choice.not_a_port"), description: t("ports.choice.notAPortHelp") },
              ]}
            />
          </div>

          {interpretation === "port" && (
            <div className="review-form__group">
              <div id="port-choice" tabIndex={-1}>
                <ChoiceGroup<PortChoice>
                  legend={t("ports.which")}
                  value={portChoice}
                  onValueChange={(value) => {
                    setPortChoice(value);
                    if (value === "existing" && !existing && data.suggested_port) setExisting(data.suggested_port);
                  }}
                  choices={[
                    {
                      value: "existing",
                      label: t("ports.which.existing"),
                      description: data.suggested_port
                        ? t("ports.which.existingSuggested", { name: portName(i18n, data.suggested_port) })
                        : t("ports.which.existingHelp"),
                    },
                    ...(listPosition
                      ? [
                          {
                            value: "from_list" as const,
                            label: t("ports.which.fromList"),
                            description: t("ports.which.fromListHelp", { position: coordinates(i18n, listPosition) }),
                          },
                        ]
                      : []),
                    { value: "enter", label: t("ports.which.enter"), description: t("ports.which.enterHelp") },
                  ]}
                />
              </div>
              {portChoice === "existing" && (
                <div id="port-existing" tabIndex={-1}>
                  <PortSearch label={t("ports.search")} value={existing} onValueChange={setExisting} />
                  {errorFor("port-existing") && <p className="ui-field__error">{errorFor("port-existing")}</p>}
                </div>
              )}
              {portChoice === "enter" && (
                <div className="workspace-coordinates">
                  <TextField
                    id="port-latitude"
                    label={t("ports.latitude")}
                    description={t("ports.latitudeHelp")}
                    inputMode="decimal"
                    value={latitude}
                    onChange={(event) => setLatitude(event.target.value)}
                    error={errorFor("port-latitude")}
                  />
                  <TextField
                    id="port-longitude"
                    label={t("ports.longitude")}
                    description={t("ports.longitudeHelp")}
                    inputMode="decimal"
                    value={longitude}
                    onChange={(event) => setLongitude(event.target.value)}
                    error={errorFor("port-longitude")}
                  />
                </div>
              )}
              {(portChoice === "enter" || portChoice === "from_list") && (
                <TextField
                  id="port-country"
                  label={t("ports.country")}
                  description={t("ports.countryHelp")}
                  optional
                  maxLength={2}
                  autoCapitalize="characters"
                  value={country}
                  onChange={(event) => setCountry(event.target.value)}
                  error={errorFor("port-country")}
                />
              )}
            </div>
          )}

          {interpretation === "ports" && (
            <div className="review-form__group" id="port-several" tabIndex={-1}>
              <PortSearch
                label={t("ports.addPort")}
                value={null}
                onValueChange={(port) => {
                  if (port && !several.some((item) => item.id === port.id)) setSeveral([...several, port]);
                }}
              />
              {several.length > 0 && (
                <ul className="workspace-chips" aria-label={t("ports.chosen")}>
                  {several.map((port) => (
                    <li key={port.id}>
                      {portName(i18n, port)}{" "}
                      <Button
                        size="sm"
                        variant="quiet"
                        aria-label={t("ports.remove", { name: port.name })}
                        onClick={() => setSeveral(several.filter((item) => item.id !== port.id))}
                      >
                        ×
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              {errorFor("port-several") && <p className="ui-field__error">{errorFor("port-several")}</p>}
            </div>
          )}

          {interpretation === "vessel" && (
            <div className="review-form__group" id="port-vessel" tabIndex={-1}>
              {availableVessels.length ? (
                <SelectField<string>
                  label={t("ports.vessel")}
                  value={vessel}
                  emptyLabel={t("imports.new.choose")}
                  options={availableVessels.map((item) => ({ value: item.id, label: item.name }))}
                  onValueChange={setVessel}
                />
              ) : (
                <InlineMessage tone="warning">{t("ports.choice.vesselNone")}</InlineMessage>
              )}
              {errorFor("port-vessel") && <p className="ui-field__error">{errorFor("port-vessel")}</p>}
            </div>
          )}

          <TextField
            id="port-reason"
            label={t("review.reason")}
            description={t("ports.reasonHelp")}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            error={errorFor("port-reason")}
          />
          <p className="review-note">{t("ports.effect")}</p>
          <div className="workspace-actions">
            <Button variant="primary" loading={saving} onClick={() => void submit(false)}>
              {t("ports.save")}
            </Button>
            <Button loading={saving} onClick={() => void submit(true)}>
              {t("ports.saveNext")}
            </Button>
          </div>
        </form>
      )}
    </article>
  );
}

