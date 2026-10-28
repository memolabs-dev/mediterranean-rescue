import { api, type Me } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { InlineMessage, PendingState } from "../ui/Feedback";
import { Icon } from "../ui/Icon";
import { Decide } from "./PublicationDecision";
import { Prepare } from "./PublicationPrepare";
import { WorkspaceShell } from "./WorkspaceShell";

// Two named decisions take a verified event to the public site: prepare (a private copy), then
// publish. Each asks for a short reason, kept with the event (ADR 0013).
export function PublishWorkspace() {
  const { t } = useI18n();
  return (
    <WorkspaceShell section="publish" title={t("publish.title")} className="review review--wide">
      {(me) => <Publish me={me} />}
    </WorkspaceShell>
  );
}

function Publish({ me }: { me: Me }) {
  const { t } = useI18n();
  const overview = api.useQuery("get", "/api/private/v1/publication/", {});
  if (overview.error) return <InlineMessage tone="error">{t("workspace.loadError")}</InlineMessage>;
  if (!overview.data) return <PendingState label={t("workspace.loading")} />;
  const data = overview.data;
  const locked = data.sources.filter((source) => !source.rights_approved);
  return (
    <div className="publish">
      <div className="team-home__head">
        <h1>{t("publish.title")}</h1>
        <p>{t("publish.lead")}</p>
      </div>
      {locked.length > 0 && (
        <div className="publish-lock" role="status">
          <Icon name="lock" size={22} />
          <div>
            <h2>{t(locked.length === data.sources.length ? "publish.locked.title" : "publish.locked.someTitle")}</h2>
            <p>
              {t(locked.length === data.sources.length ? "publish.locked.body" : "publish.locked.someBody", {
                sources: locked.map((source) => (source.key === "sos-logbook" ? t("logbook.sourceName") : source.name)).join(", "),
              })}
            </p>
          </div>
        </div>
      )}
      <Prepare overview={data} />
      <Decide
        canPublish={data.can.publish}
        counts={data.events}
        ready={data.preparation.reduce((sum, item) => sum + item.ready, 0)}
        reviewer={me.permissions.review_identity}
      />
    </div>
  );
}

