import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorCode, fetchClient, type PublicationOverview } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { Button } from "../ui/Button";
import { InlineMessage } from "../ui/Feedback";
import { TextField } from "../ui/TextField";
import { failure, OVERVIEW } from "./publicationShared";
import { ME_QUERY } from "./WorkspaceShell";

// First human decision: create *private* drafts from reviewed source rows.
// No call here can publish an event; publication is a second, authorized step.
export function Prepare({ overview }: { overview: PublicationOverview }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const total = (key: "ready" | "changed" | "not_verified" | "to_fix") => overview.preparation.reduce((sum, item) => sum + item[key], 0);
  const ready = total("ready");

  const prepare = async () => {
    setSaving(true);
    setMessage(null);
    try {
      // A write is never aborted; the overview is replaced by the one the server returns.
      const { data, error } = await fetchClient.POST("/api/private/v1/publication/prepare/", { body: { reason: reason.trim() } });
      if (error) throw error;
      queryClient.setQueryData(api.queryOptions(...OVERVIEW, {}).queryKey, data.overview);
      await queryClient.invalidateQueries({
        queryKey: ["get", "/api/private/v1/publication/events/"],
      });
      setReason("");
      setMessage({
        tone: "success",
        text: t("publish.prepare.done", { count: data.created }),
      });
    } catch (error) {
      setMessage({ tone: "error", text: failure(t, error) });
      void queryClient.invalidateQueries({ queryKey: [...OVERVIEW] });
      if (errorCode(error) === "not_authenticated") void queryClient.invalidateQueries({ queryKey: ME_QUERY });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="publish-step" aria-labelledby="prepare-title">
      <p className="publish-step__eyebrow">{t("publish.step", { number: 1 })}</p>
      <h2 id="prepare-title">{t("publish.prepare.title")}</h2>
      <p className="publish-step__why">{t("publish.prepare.why")}</p>
      <ul className="publish-counts">
        <li className="publish-counts__main">
          <b>{ready}</b> {t("publish.prepare.ready", { count: ready })}
        </li>
        {total("not_verified") > 0 && (
          <li>
            <Link to="/workspace/review">
              {t("publish.prepare.notVerified", {
                count: total("not_verified"),
              })}
            </Link>
          </li>
        )}
        {total("to_fix") > 0 && <li>{t("publish.prepare.toFix", { count: total("to_fix") })}</li>}
        {total("changed") > 0 && <li>{t("publish.prepare.changed", { count: total("changed") })}</li>}
      </ul>
      {!overview.can.prepare ? (
        <InlineMessage tone="info">{t("publish.prepare.notAllowed")}</InlineMessage>
      ) : ready > 0 ? (
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (reason.trim()) void prepare();
          }}
        >
          <TextField
            label={t("publish.reason")}
            description={t("publish.prepare.reasonHelp")}
            value={reason}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
          />
          <Button type="submit" loading={saving} disabled={!reason.trim()}>
            {t("publish.prepare.action", { count: ready })}
          </Button>
        </form>
      ) : null}
      {message && <InlineMessage tone={message.tone}>{message.text}</InlineMessage>}
    </section>
  );
}

