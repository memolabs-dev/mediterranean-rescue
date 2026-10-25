import { useState } from "react";
import { api, errorCode } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Button } from "../ui/Button";
import { InlineMessage } from "../ui/Feedback";
import { TextField } from "../ui/TextField";

export function VolunteerCredentials() {
  const { t } = useI18n();
  const status = api.useQuery("get", "/api/private/v1/credentials/");
  const setup = api.useMutation("post", "/api/private/v1/credentials/");
  const [value, setValue] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [done, setDone] = useState(false);
  const [failure, setFailure] = useState("");
  if (done) return <p role="status">{t("credentials.success")}</p>;
  if (!status.data?.needs_setup) return null;
  const lengthOk = value.length >= 12 && value.length <= 128;
  const same = confirmation !== "" && value === confirmation;
  return (
    <section className="workspace-panel" aria-labelledby="credentials-title">
      <h2 id="credentials-title">{t("credentials.title")}</h2>
      <p className="workspace-lead">{t("credentials.lead")}</p>
      <form className="team-invite" noValidate onSubmit={async (event) => {
        event.preventDefault();
        setAttempted(true);
        setFailure("");
        if (!lengthOk || !same) return;
        try {
          await setup.mutateAsync({ body: { password: value, confirmation } });
          setValue("");
          setConfirmation("");
          setDone(true);
        } catch (error) {
          setFailure(t(errorCode(error) === "invalid" ? "credentials.weak" : "credentials.failed"));
        }
      }}>
        <TextField label={t("credentials.password")} type="password" autoComplete="new-password"
          value={value} onChange={(e) => setValue(e.target.value)}
          description={t("credentials.length")}
          error={attempted && !lengthOk ? t("credentials.length") : null} />
        <TextField label={t("credentials.confirmation")} type="password" autoComplete="new-password"
          value={confirmation} onChange={(e) => setConfirmation(e.target.value)}
          error={attempted && !same ? t("credentials.mismatch") : null} />
        {failure && <InlineMessage tone="error">{failure}</InlineMessage>}
        <Button type="submit" variant="primary" loading={setup.isPending}>{t("credentials.save")}</Button>
      </form>
    </section>
  );
}
