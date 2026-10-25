import { useEffect } from "react";
import { useI18n, type I18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { Icon, type IconName } from "../ui/Icon";
import { markJourney } from "./journey";
import { WorkspaceShell } from "./WorkspaceShell";

type Key = Parameters<I18n["t"]>[0];

const GUIDES: { key: string; icon: IconName }[] = [
  { key: "verify", icon: "listCheck" },
  { key: "doubt", icon: "alert" },
  { key: "publish", icon: "send" },
  { key: "words", icon: "help" },
];

// Short answers to what a volunteer asks while working: what is expected, why, an example. No
// manual to read first; each guide fits on a phone screen.
function Guides({ username }: { username: string }) {
  const { t } = useI18n();
  // Reading how publication works is a step of the volunteer's first journey.
  useEffect(() => markJourney("publishGuide", username), [username]);
  return (
    <div className="help">
      <div className="practice__head">
        <h1>{t("help.title")}</h1>
        <p>{t("help.lead")}</p>
      </div>
      <div className="help__guides">
        {GUIDES.map((guide) => (
          <section key={guide.key} className="help__guide" aria-labelledby={`help-${guide.key}`}>
            <h2 id={`help-${guide.key}`}>
              <Icon name={guide.icon} size={20} />
              {t(`help.${guide.key}.title` as Key)}
            </h2>
            <p>{t(`help.${guide.key}.what` as Key)}</p>
            <p className="help__why">
              <b>{t("help.why")}</b> {t(`help.${guide.key}.why` as Key)}
            </p>
            <p className="help__example">
              <b>{t("help.example")}</b> {t(`help.${guide.key}.example` as Key)}
            </p>
          </section>
        ))}
      </div>
      <p className="review-note">
        <Link to="/workspace/practice">{t("help.practice")}</Link> · <Link to="/about">{t("help.about")}</Link>
      </p>
    </div>
  );
}

export function TeamHelp() {
  const { t } = useI18n();
  return (
    <WorkspaceShell section="help" title={t("workspace.section.help")} className="review">
      {(me) => <Guides key={me.username} username={me.username} />}
    </WorkspaceShell>
  );
}
