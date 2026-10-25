import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorCode } from "../api/client";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { Button } from "../ui/Button";
import { Checkbox } from "../ui/Checkbox";
import { InlineMessage } from "../ui/Feedback";
import { Icon } from "../ui/Icon";
import { TextField } from "../ui/TextField";
import { WorkspaceShell } from "./WorkspaceShell";

type Key = Parameters<I18n["t"]>[0];

interface Created {
  link: string;
  email: string;
  expires: string;
}

// The coordinator's screen: invite a volunteer by link, see who joined, take back a link that has
// not served (ADR 0015). The application sends no email: the coordinator sends the link.
function InviteForm({ roles, onCreated }: { roles: { id: number; key: string }[]; onCreated: (created: Created) => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const create = api.useMutation("post", "/api/private/v1/invitations/");
  const [email, setEmail] = useState("");
  const [chosen, setChosen] = useState<number[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const submit = async () => {
    setSubmitted(true);
    setFailure(null);
    if (!emailOk || chosen.length === 0) return;
    try {
      const created = await create.mutateAsync({ body: { email: email.trim(), roles: chosen } });
      onCreated({ link: `${window.location.origin}/invite#${created.token}`, email: email.trim(), expires: created.expires_at });
      setEmail("");
      setChosen([]);
      setSubmitted(false);
      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/invitations/"] });
    } catch (error) {
      const code = errorCode(error);
      setFailure(t(code === "account_not_allowed" || code === "role_not_allowed" ? (`team.error.${code}` as Key) : "team.error.failed"));
    }
  };

  return (
    <form
      className="team-invite"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <h2>{t("team.invite.title")}</h2>
      <p className="review-note">{t("team.invite.lead")}</p>
      {failure && <InlineMessage tone="error">{failure}</InlineMessage>}
      <TextField
        label={t("team.invite.email")}
        type="email"
        autoComplete="off"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={submitted && !emailOk ? t("team.invite.emailMissing") : null}
      />
      <fieldset
        className="team-invite__roles"
        aria-invalid={submitted && chosen.length === 0 ? "true" : undefined}
        aria-describedby={submitted && chosen.length === 0 ? "team-invite-role-error" : undefined}
      >
        <legend>{t("team.invite.roles")}</legend>
        {roles.map((role) => (
          <Checkbox
            key={role.id}
            label={t(`role.${role.key}` as Key)}
            checked={chosen.includes(role.id)}
            onCheckedChange={(checked) => setChosen(checked ? [...chosen, role.id] : chosen.filter((id) => id !== role.id))}
          />
        ))}
        <p className="review-note">{t("team.invite.rolesHelp")}</p>
        {submitted && chosen.length === 0 && (
          <div id="team-invite-role-error">
            <InlineMessage tone="error">{t("team.invite.roleMissing")}</InlineMessage>
          </div>
        )}
      </fieldset>
      <Button type="submit" variant="primary" size="lg" loading={create.isPending}>
        {t("team.invite.submit")}
      </Button>
    </form>
  );
}

function CreatedLink({ created, onDone }: { created: Created; onDone: () => void }) {
  const i18n = useI18n();
  const { t } = i18n;
  const [copied, setCopied] = useState<"no" | "yes" | "failed">("no");
  const mail = `mailto:${encodeURIComponent(created.email)}?subject=${encodeURIComponent(t("team.mail.subject"))}&body=${encodeURIComponent(
    t("team.mail.body", { link: created.link }),
  )}`;
  return (
    <section className="team-created" aria-labelledby="team-created-title">
      <h2 id="team-created-title">
        <Icon name="check" size={18} /> {t("team.created.title", { email: created.email })}
      </h2>
      <p className="review-note">{t("team.created.lead", { date: i18n.date(created.expires.slice(0, 10)) })}</p>
      <p className="team-created__link">{created.link}</p>
      <div className="team-created__actions">
        <Button
          variant="primary"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(created.link);
              setCopied("yes");
            } catch {
              setCopied("failed");
            }
          }}
        >
          <Icon name="link" size={16} /> {t("team.created.copy")}
        </Button>
        <a className="pill-button" href={mail}>
          {t("team.created.mail")}
        </a>
        <Button variant="quiet" onClick={onDone}>
          {t("team.created.done")}
        </Button>
      </div>
      <p role="status" className="review-note">
        {copied === "yes" ? t("team.created.copied") : copied === "failed" ? t("team.created.copyFailed") : ""}
      </p>
    </section>
  );
}

function Invitations() {
  const i18n = useI18n();
  const { t } = i18n;
  const queryClient = useQueryClient();
  const list = api.useQuery("get", "/api/private/v1/invitations/", {});
  const revoke = api.useMutation("delete", "/api/private/v1/invitations/{id}/");
  const [created, setCreated] = useState<Created | null>(null);
  if (list.error) return <InlineMessage tone="error">{t("team.error.load")}</InlineMessage>;
  if (!list.data) return <p className="review-note">{t("team.loading")}</p>;
  return (
    <div className="team">
      {created ? <CreatedLink created={created} onDone={() => setCreated(null)} /> : <InviteForm roles={list.data.roles} onCreated={setCreated} />}
      <section aria-labelledby="team-list-title" className="team-list">
        <h2 id="team-list-title">{t("team.list.title")}</h2>
        {list.data.items.length === 0 ? (
          <p className="review-note">{t("team.list.empty")}</p>
        ) : (
          <ul>
            {list.data.items.map((invitation) => (
              <li key={invitation.id} className="team-list__item">
                <div>
                  <p className="team-list__email">{invitation.email}</p>
                  <p className="review-note">
                    {invitation.roles.length ? invitation.roles.map((role) => t(`role.${role}` as Key)).join(" · ") : t("team.list.noRole")}
                  </p>
                  <p className="review-note">
                    {t(`team.status.${invitation.status}` as Key, {
                      date: i18n.date(invitation.expires_at.slice(0, 10)),
                      name: invitation.used_by ?? "",
                    })}
                  </p>
                </div>
                {invitation.status === "waiting" && (
                  <Button
                    size="sm"
                    variant="quiet"
                    loading={revoke.isPending && revoke.variables?.params.path.id === invitation.id}
                    onClick={async () => {
                      await revoke.mutateAsync({ params: { path: { id: invitation.id } } });
                      await queryClient.invalidateQueries({ queryKey: ["get", "/api/private/v1/invitations/"] });
                    }}
                  >
                    {t("team.list.revoke")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function TeamPeople() {
  const { t } = useI18n();
  return (
    <WorkspaceShell section="team" title={t("workspace.section.team")} className="review">
      {() => <Invitations />}
    </WorkspaceShell>
  );
}
