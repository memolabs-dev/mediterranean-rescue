import { useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { Link } from "../router";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { markJourney } from "./journey";
import { WorkspaceShell } from "./WorkspaceShell";

type Step = "look" | "act" | "done";

// A first verification on an invented operation, with one mistake to spot: the volunteer learns
// the gesture before touching real data, and nothing is sent anywhere (25 October 2026).
function Exercise({ username }: { username: string }) {
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("look");
  const [feedback, setFeedback] = useState<"right" | "wrong" | null>(null);

  const answer = (right: boolean, next: Step) => {
    setFeedback(right ? "right" : "wrong");
    if (right) {
      if (next === "done") markJourney("practice", username);
      setStep(next);
    }
  };

  return (
    <div className="practice">
      <div className="practice__head">
        <h1>{t("practice.title")}</h1>
        <p>{t("practice.lead")}</p>
        <p className="practice__safe">
          <Icon name="lock" size={16} /> {t("practice.safe")}
        </p>
      </div>

      <section className="practice__case" aria-labelledby="practice-case">
        <h2 id="practice-case">{t("practice.case.title")}</h2>
        <div className="logbook-evidence">
          <p className="logbook-evidence__label">{t("practice.case.label")}</p>
          <blockquote lang="en">{t("practice.case.quote")}</blockquote>
        </div>
        <h3>{t("practice.case.read")}</h3>
        <dl className="review-facts">
          <div>
            <dt>{t("review.field.date")}</dt>
            <dd>{t("practice.case.date")}</dd>
          </div>
          <div>
            <dt>{t("review.field.nb_survivor")}</dt>
            <dd className={step !== "look" ? "practice__wrong" : undefined}>45</dd>
          </div>
          <div>
            <dt>{t("review.field.position")}</dt>
            <dd>{t("practice.case.position")}</dd>
          </div>
        </dl>
      </section>

      {step === "look" && (
        <section className="practice__question" aria-labelledby="practice-q1">
          <h2 id="practice-q1">{t("practice.q1")}</h2>
          <div className="practice__answers">
            <Button size="lg" onClick={() => answer(false, "act")}>
              {t("practice.q1.yes")}
            </Button>
            <Button size="lg" onClick={() => answer(true, "act")}>
              {t("practice.q1.no")}
            </Button>
          </div>
          {feedback === "wrong" && (
            <p className="practice__feedback practice__feedback--wrong" role="status">
              {t("practice.q1.hint")}
            </p>
          )}
        </section>
      )}

      {step === "act" && (
        <section className="practice__question" aria-labelledby="practice-q2">
          <p className="practice__feedback practice__feedback--right" role="status">
            <Icon name="check" size={16} /> {t("practice.q1.right")}
          </p>
          <h2 id="practice-q2">{t("practice.q2")}</h2>
          <div className="practice__answers practice__answers--stack">
            <Button size="lg" onClick={() => answer(false, "act")}>
              {t("practice.q2.verify")}
            </Button>
            <Button size="lg" onClick={() => answer(true, "done")}>
              {t("practice.q2.later")}
            </Button>
          </div>
          {feedback === "wrong" && (
            <p className="practice__feedback practice__feedback--wrong" role="status">
              {t("practice.q2.hint")}
            </p>
          )}
        </section>
      )}

      {step === "done" && (
        <section className="practice__question practice__question--done" aria-labelledby="practice-done">
          <h2 id="practice-done">
            <Icon name="check" size={20} /> {t("practice.done.title")}
          </h2>
          <p>{t("practice.done.body")}</p>
          <Link to="/workspace" className="pill-button pill-button--primary">
            {t("practice.done.next")}
            <Icon name="arrowRight" size={16} />
          </Link>
        </section>
      )}
    </div>
  );
}

export function TeamPractice() {
  const { t } = useI18n();
  return (
    <WorkspaceShell section="practice" title={t("workspace.section.practice")} className="review">
      {(me) => <Exercise key={me.username} username={me.username} />}
    </WorkspaceShell>
  );
}
