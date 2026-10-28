import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { Kind } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

const EventMap = lazy(async () => ({ default: (await import("../components/Map")).EventMap }));

export function MapPanel({
  points,
  activeId,
  focusId,
  followId,
  onSelect,
  truncated,
  insetBottom = 0,
}: {
  points: { id: string; longitude: number; latitude: number; kind: Kind }[];
  activeId: string | null;
  focusId: string | null;
  followId: string | null;
  onSelect: (id: string) => void;
  truncated: boolean;
  insetBottom?: number;
}) {
  const { t } = useI18n();
  const placeholder = useRef<HTMLDivElement>(null);
  // Do not download MapLibre, its worker or coastline for an off-screen mobile map.
  const [nearby, setNearby] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    if (nearby || !placeholder.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => { if (entries.some((entry) => entry.isIntersecting)) setNearby(true); },
      { rootMargin: "180px" },
    );
    observer.observe(placeholder.current);
    return () => observer.disconnect();
  }, [nearby]);
  return (
    <div className="map-card" ref={placeholder}>
      {nearby ? (
        <Suspense fallback={<div className="map-card__loading">{t("map.loading")}</div>}>
          <EventMap points={points} onSelect={onSelect} activeId={activeId} focusId={focusId} followId={followId} insetBottom={insetBottom} />
        </Suspense>
      ) : (
        <div className="map-card__loading" role="status">{t("map.loading")}</div>
      )}
      {truncated && <p className="map-card__note">{t("map.truncated")}</p>}
    </div>
  );
}

