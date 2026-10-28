import { Button as BaseButton } from "@base-ui/react/button";
import { useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { formatPosition } from "../shared/geo";
import { Icon } from "../ui/Icon";
import { PreviewBody, PublicBody } from "./EventBody";
import { kindName, peopleText, type Key } from "./labels";
import { MiniMap } from "./MiniMap";
import type { FeedItem, Status } from "./types";

// Short labels for the card badge; the full sentence stays in the opened record.
function statusKey(status: Status): Key {
  return `explore.status.${status}` as Key;
}

export function EventCard({
  item,
  preview,
  open,
  onToggle,
  onHover,
}: {
  item: FeedItem;
  preview: boolean;
  open: boolean;
  onToggle: () => void;
  onHover: (hovered: boolean) => void;
}) {
  const i18n = useI18n();
  const { t } = i18n;
  const ref = useRef<HTMLLIElement>(null);
  const bodyId = `event-${item.id}-body`;
  return (
    <li
      id={`event-${item.id}`}
      ref={ref}
      className={`card${open ? " card--open" : ""}`}
      data-kind={item.kind ?? undefined}
      onPointerEnter={(event) => event.pointerType === "mouse" && onHover(true)}
      onPointerLeave={(event) => event.pointerType === "mouse" && onHover(false)}
    >
      <BaseButton className="card__summary" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
        <span className="card__text">
          <span className="card__top">
            <span className="card__date">{item.date ? i18n.date(item.date) : t("review.unknown")}</span>
            {item.status && (
              <span className={`status status--${item.status}`}>
                <i aria-hidden="true" />
                {t(statusKey(item.status))}
              </span>
            )}
          </span>
          <span className="card__kind">
            <i className="card__kind-dot" aria-hidden="true" />
            {kindName(i18n, item.kind)}
          </span>
          <span className="card__facts">
            <span className="card__people">
              <Icon name="people" size={17} />
              {peopleText(i18n, item.kind, item.people)}
            </span>
            {item.port && (
              <span className="card__port">
                <Icon name="anchor" size={16} />
                {item.port}
              </span>
            )}
          </span>
          <span className="card__origin">{item.origin}</span>
        </span>
        <span className="card__locator">
          <MiniMap
            position={item.position}
            label={item.position ? formatPosition(i18n, item.position.latitude, item.position.longitude) : t("map.unknownPosition")}
            unknownLabel={t("map.unknownPosition")}
          />
        </span>
        <Icon name="chevronDown" className="card__chevron" />
      </BaseButton>
      <div id={bodyId} className="card__body" role="region" aria-label={t("detail.title")} hidden={!open}>
        {open && (
          <>
            {preview ? <PreviewBody id={item.id} /> : <PublicBody id={item.id} />}
            <CopyLink id={item.id} />
          </>
        )}
      </div>
    </li>
  );
}

export function PinnedCard({ id, from, preview, onClose }: { id: string; from: "link" | "map"; preview: boolean; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="card card--open card--pinned">
      <div className="card__pinned-head">
        <span>
          <Icon name={from === "map" ? "pin" : "link"} size={16} /> {t(from === "map" ? "explore.fromMap" : "explore.fromLink")}
        </span>
        <BaseButton className="icon-button" aria-label={t("ui.close")} onClick={onClose}>
          <Icon name="close" size={18} />
        </BaseButton>
      </div>
      <div className="card__body">
        {preview ? <PreviewBody id={id} /> : <PublicBody id={id} />}
        <CopyLink id={id} />
      </div>
    </div>
  );
}

// The address of one record, to share or cite. Without clipboard access the link is shown instead.
function CopyLink({ id }: { id: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<"idle" | "copied" | "shown">("idle");
  const url = `${window.location.origin}${window.location.pathname}?event=${id}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setState("copied");
    } catch {
      setState("shown");
    }
  };
  return (
    <p className="card__link">
      <BaseButton className="link-button" onClick={() => void copy()}>
        <Icon name="link" size={16} />
        {t("explore.copyLink")}
      </BaseButton>
      <span role="status">
        {state === "copied" && t("explore.linkCopied")}
        {state === "shown" && <a href={url}>{url}</a>}
      </span>
    </p>
  );
}
