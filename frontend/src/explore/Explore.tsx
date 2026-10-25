import { Button as BaseButton } from "@base-ui/react/button";
import { lazy, Suspense, useEffect, useRef, useState, type FocusEvent } from "react";
import { keepPreviousData } from "@tanstack/react-query";
import { api, type Kind } from "../api/client";
import { kinds } from "../filters";
import { useI18n } from "../i18n/I18nProvider";
import { changeQuery, Link, useLocation } from "../router";
import { formatPosition } from "../shared/geo";
import { Icon } from "../ui/Icon";
import { PreviewBody, PublicBody } from "./EventBody";
import { fromNewsSite, missionName } from "./Evidence";
import { kindLabel, kindName, peopleText, type Key } from "./labels";
import { Logbook } from "./Logbook";
import { MapPeek } from "./MapPeek";
import { MiniMap } from "./MiniMap";
import { PublicBar } from "./PublicBar";
import { Welcome } from "./Welcome";
import { Timeline } from "./Timeline";

const EventMap = lazy(async () => ({ default: (await import("../components/Map")).EventMap }));
const PAGE = 25;
const LOGBOOK_SOURCE = "sos-logbook";
// Three ways to read the same events.
type View = "feed" | "logbook" | "timeline";
const VIEWS: readonly { value: View; icon: "map" | "calendar" | "anchor" }[] = [
  { value: "feed", icon: "anchor" },
  { value: "logbook", icon: "calendar" },
  { value: "timeline", icon: "map" },
];
type Status = "to_review" | "blocked" | "linked";

/** One feed entry, from a published event or from a row of the private export. */
interface FeedItem {
  id: string;
  date: string | null;
  kind: string | null;
  people: number | null;
  port: string | null;
  position: { longitude: number; latitude: number } | null;
  title: string | null;
  status: Status | null;
  line: number | null;
  /** Where the record comes from, shown on the closed card: the source, or the export row. */
  origin: string;
}

function useDebounced<T>(value: T, delay: number) {
  const [current, setCurrent] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setCurrent(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return current;
}

/** Height of an element, kept current while it resizes; 0 when there is none. */
function useHeight(element: HTMLElement | null) {
  const [height, setHeight] = useState(0);
  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setHeight(Math.round(entry?.borderBoxSize[0]?.blockSize ?? element.offsetHeight)));
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return element ? height : 0;
}

// The same reading screen for two audiences, never mixed: "public" shows only published events;
// "team" (inside the team space) shows the latest data received, with its review state.
export function Explore({ audience = "public" }: { audience?: "public" | "team" }) {
  const i18n = useI18n();
  const { t } = i18n;
  const preview = audience === "team";
  const { query } = useLocation();
  const requested = VIEWS.find((item) => item.value === query.get("view"));
  const view: View = requested?.value ?? "feed";

  const [text, setText] = useState("");
  const q = useDebounced(text.trim(), 300);
  const [kind, setKind] = useState<Kind | "">("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [periodOpen, setPeriodOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(true);
  // A record can be linked to: "?event=<id>" opens it, pinned on top until the feed holds it.
  const linkedId = eventParam(query.get("event"));
  const [openId, setOpenId] = useState<string | null>(linkedId);
  const [pinnedId, setPinnedId] = useState<string | null>(linkedId);
  const [pinnedFrom, setPinnedFrom] = useState<"link" | "map">("link");
  // Phones and tablets: a tapped point is previewed over the map, which can fill the screen.
  const [peekId, setPeekId] = useState<string | null>(null);
  const [mapFull, setMapFull] = useState(false);
  const show = (id: string | null) => {
    setOpenId(id);
    changeQuery({ event: id }, { replace: true });
  };
  // The card under the pointer lights its point; the open card wins over it.
  const [hoverId, setHoverId] = useState<string | null>(null);
  // In the logbook, the entry being read; the map follows it.
  const [readId, setReadId] = useState<string | null>(null);
  const invalid = Boolean(start && end && start > end);
  const filters = {
    ...(start ? { start } : {}),
    ...(end ? { end } : {}),
    ...(kind ? { kind } : {}),
    ...(q ? { q } : {}),
  };
  // Team only: the operations rebuilt from the public logbook, alone (ADR 0014).
  const logbookOnly = preview && query.get("source") === LOGBOOK_SOURCE;
  const teamFilters = { ...filters, ...(logbookOnly ? { source: LOGBOOK_SOURCE } : {}) };

  const page = (all: readonly unknown[], last: { has_next: boolean }) => (last.has_next ? all.length * PAGE : undefined);
  const publicFeed = api.useInfiniteQuery(
    "get",
    "/api/v1/events/",
    { params: { query: { ...filters, limit: PAGE } } },
    { pageParamName: "offset", initialPageParam: 0, getNextPageParam: (last, all) => page(all, last), enabled: !invalid && !preview },
  );
  const previewFeed = api.useInfiniteQuery(
    "get",
    "/api/private/v1/preview/events/",
    { params: { query: { ...teamFilters, limit: PAGE } } },
    { pageParamName: "offset", initialPageParam: 0, getNextPageParam: (last, all) => page(all, last), enabled: !invalid && preview },
  );
  const publicMap = api.useQuery("get", "/api/v1/map-points/", { params: { query: filters } }, { enabled: !invalid && !preview });
  const previewMap = api.useQuery("get", "/api/private/v1/preview/map-points/", { params: { query: teamFilters } }, { enabled: !invalid && preview });

  // The timeline counts every month for the kind and words chosen; the period is what it selects.
  const timelineFilters = { ...(kind ? { kind } : {}), ...(q ? { q } : {}) };
  // The previous counts stay on screen while new ones load, so the timeline never blinks away.
  const publicTimeline = api.useQuery(
    "get",
    "/api/v1/timeline/",
    { params: { query: timelineFilters } },
    { enabled: view === "timeline" && !preview, placeholderData: keepPreviousData },
  );
  const previewTimeline = api.useQuery(
    "get",
    "/api/private/v1/preview/timeline/",
    { params: { query: { ...timelineFilters, ...(logbookOnly ? { source: LOGBOOK_SOURCE } : {}) } } },
    { enabled: view === "timeline" && preview, placeholderData: keepPreviousData },
  );
  const timelineQuery = preview ? previewTimeline : publicTimeline;
  const timeline = timelineQuery.data;
  const undated = preview ? (previewTimeline.data?.undated ?? 0) : 0;
  // The map beside the overlaid timeline centres above it.
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  const overlayHeight = useHeight(overlay);
  const feed = preview ? previewFeed : publicFeed;
  const map = preview ? previewMap.data : publicMap.data;
  const items: FeedItem[] = preview
    ? (previewFeed.data?.pages ?? []).flatMap((p) =>
        p.items.map((row) => ({
          id: row.id,
          date: row.occurred_on,
          kind: row.kind,
          people: row.people,
          port: row.port_label,
          position: row.position,
          title: null,
          status: row.status as Status,
          line: row.line,
          origin: row.evidence
            ? fromNewsSite(row.evidence)
              ? t("explore.origin.news")
              : t("explore.origin.logbook", { rotation: missionName(i18n, row.evidence.rotation ?? "") })
            : t("explore.origin.update", { date: i18n.date(row.exported_at ? row.exported_at.slice(0, 10) : "") }),
        })),
      )
    : (publicFeed.data?.pages ?? []).flatMap((p) =>
        p.items.map((event) => ({
          id: event.id,
          date: event.occurred_on,
          kind: event.kind,
          people: event.people,
          port: event.port?.name ?? null,
          position: event.position,
          title: event.title,
          status: null,
          line: null,
          origin: t("explore.origin.source", { source: event.source.name }),
        })),
      );
  const total = preview ? previewFeed.data?.pages[0]?.total_count : publicFeed.data?.pages[0]?.total_count;
  const counts = previewFeed.data?.pages[0]?.counts;
  const trainingData = !preview && publicFeed.data?.pages[0]?.data_mode === "training";
  const points = (map?.points ?? []).map((point) => ({
    id: point.id,
    longitude: point.longitude,
    latitude: point.latitude,
    kind: point.kind as Kind,
  }));
  const followId = view === "logbook" ? readId : null;
  const activeId = openId ?? peekId ?? pinnedId ?? hoverId ?? followId;
  const filtered = Boolean(kind || start || end || q || logbookOnly);

  // A linked record is brought into view once, when the feed first arrives.
  const loaded = Boolean(feed.data);
  const broughtIntoView = useRef(false);
  useEffect(() => {
    if (!loaded || !linkedId || broughtIntoView.current) return;
    broughtIntoView.current = true;
    requestAnimationFrame(() =>
      (document.getElementById(`event-${linkedId}`) ?? document.getElementById("pinned-event"))?.scrollIntoView?.({ block: "start" }),
    );
  }, [loaded, linkedId]);

  useEffect(() => {
    document.title = t("app.documentTitle");
    document.querySelector('meta[name="description"]')?.setAttribute("content", t("app.metaDescription"));
  }, [t]);

  const resetView = () => {
    show(null);
    setPinnedId(null);
  };
  const clearFilters = () => {
    setText("");
    setKind("");
    setStart("");
    setEnd("");
    if (logbookOnly) changeQuery({ source: null }, { replace: true });
    resetView();
  };
  // Full screen map: Escape leaves it, and the page behind does not scroll meanwhile.
  useEffect(() => {
    if (!mapFull) return;
    const leave = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMapFull(false);
    };
    document.documentElement.classList.add("map-full-open");
    window.addEventListener("keydown", leave);
    return () => {
      document.documentElement.classList.remove("map-full-open");
      window.removeEventListener("keydown", leave);
    };
  }, [mapFull]);

  // On a phone or tablet the map sits above the feed: a tapped point is previewed over the map so
  // the reader keeps it; on a desk the map stays beside the feed and the card opens at once.
  const selectFromMap = (id: string) => {
    if (window.matchMedia?.("(max-width: 959px)").matches) setPeekId(id);
    else openRecord(id);
  };
  // Opens a record in the feed, or pins it on top when the feed does not hold it.
  const openRecord = (id: string) => {
    show(id);
    if (items.some((item) => item.id === id)) {
      setPinnedId(null);
      requestAnimationFrame(() => document.getElementById(`event-${id}`)?.scrollIntoView({ behavior: motion(), block: "nearest" }));
    } else {
      setPinnedId(id);
      setPinnedFrom("map");
      requestAnimationFrame(() => document.getElementById("pinned-event")?.scrollIntoView({ behavior: motion(), block: "nearest" }));
    }
  };

  const renderTimeline = (className: string, ref?: (element: HTMLElement | null) => void) =>
    timelineQuery.error && !timeline ? (
      <p className={`timeline timeline--empty ${className}`} role="alert">
        {t("timeline.loadError")}
      </p>
    ) : timeline ? (
      <Timeline
        ref={ref}
        className={className}
        months={timeline.months}
        undated={undated}
        start={start}
        end={end}
        onPeriodChange={(from, to) => {
          setStart(from);
          setEnd(to);
          resetView();
        }}
      />
    ) : null;

  return (
    <div className={`explore${preview ? " explore--team" : ""} explore--view-${view}`}>
      {!preview && (
        <a className="skip-link" href="#explore-title">
          {t("app.skip")}
        </a>
      )}
      {!preview && <PublicBar />}

      <div className="explore-body" {...(preview ? {} : { role: "main" })}>
        <section className="explore-feed" aria-labelledby="explore-title">
          <div className="explore-intro">
            <h1 id="explore-title">{t("app.title")}</h1>
            <p>{t("app.lead")}</p>
          </div>

          {/* Fictitious data is said before anything else, on a phone too (product audit, P0). */}
          {trainingData && (
            <div className="notice-preview" role="status">
              <Icon name="alert" size={18} />
              <div>{t("app.training")}</div>
            </div>
          )}
          {!preview && <Welcome training={trainingData} />}

          <div className="composer">
            <div className="views" role="group" aria-label={t("explore.view")} onFocus={revealFocused}>
              {VIEWS.map((item) => (
                <BaseButton
                  key={item.value}
                  className="views__option"
                  aria-pressed={view === item.value}
                  onClick={() => changeQuery({ view: item.value === "feed" ? null : item.value }, { replace: true })}
                >
                  <Icon name={item.icon} size={16} />
                  {t(`explore.view.${item.value}`)}
                </BaseButton>
              ))}
            </div>
            <label className="composer__field">
              <Icon name="search" className="composer__icon" />
              <span className="sr-only">{t("explore.search")}</span>
              <input
                type="search"
                value={text}
                placeholder={t(preview ? "explore.searchPreview" : "explore.searchPublic")}
                onChange={(event) => {
                  setText(event.target.value);
                  resetView();
                }}
                enterKeyHint="search"
              />
              {text && (
                <BaseButton className="composer__clear" aria-label={t("ui.search.clear")} onClick={() => setText("")}>
                  <Icon name="close" size={16} />
                </BaseButton>
              )}
            </label>
            <div className="chips" role="group" aria-label={t("filters.kind")} onFocus={revealFocused}>
              <BaseButton className="chip" aria-pressed={kind === ""} onClick={() => setKind("")}>
                {t("filters.allKinds")}
              </BaseButton>
              {kinds.map((value) => (
                <BaseButton
                  key={value}
                  className={`chip chip--${value}`}
                  aria-pressed={kind === value}
                  onClick={() => {
                    setKind(kind === value ? "" : value);
                    resetView();
                  }}
                >
                  <i className="chip__dot" aria-hidden="true" />
                  {kindLabel(i18n, value)}
                </BaseButton>
              ))}
              {preview && (
                <BaseButton
                  className="chip chip--logbook"
                  aria-pressed={logbookOnly}
                  onClick={() => {
                    changeQuery({ source: logbookOnly ? null : LOGBOOK_SOURCE }, { replace: true });
                    resetView();
                  }}
                >
                  <Icon name="anchor" size={15} />
                  {t("logbook.chip")}
                </BaseButton>
              )}
              <BaseButton className="chip chip--period" aria-pressed={Boolean(start || end)} aria-expanded={periodOpen} onClick={() => setPeriodOpen(!periodOpen)}>
                <Icon name="calendar" size={15} />
                {start || end ? t("explore.periodSet", { from: start ? i18n.date(start) : "…", to: end ? i18n.date(end) : "…" }) : t("explore.period")}
              </BaseButton>
            </div>
            <div className="composer__period" data-open={periodOpen || undefined}>
              <div className="composer__period-inner">
                <label>
                  {t("filters.from")}
                  <input type="date" value={start} max={end || undefined} onChange={(event) => setStart(event.target.value)} />
                </label>
                <label>
                  {t("filters.to")}
                  <input type="date" value={end} min={start || undefined} onChange={(event) => setEnd(event.target.value)} />
                </label>
              </div>
            </div>
            {invalid && (
              <p role="alert" className="explore-alert">
                <Icon name="alert" size={16} /> {t("filters.invalidRange")}
              </p>
            )}
          </div>

          {view === "timeline" && renderTimeline("timeline--inline")}

          {preview && (
            <div className="preview-strip">
              {preview && (
                <div className="notice-preview" role="status">
                  <Icon name="lock" size={18} />
                  <div>
                    <strong>{t("preview.banner.title")}</strong> <span className="notice-preview__body">{t("preview.banner.body")}</span>
                    {counts && (
                      <p className="notice-preview__counts">
                        <span className="count count--to_review">{t("explore.toCheck", { count: counts.to_review })}</span>
                        <span className="count count--blocked">{t("explore.blocked", { count: counts.blocked })}</span>
                        <span className="count count--linked">{t("explore.checked", { count: counts.linked })}</span>
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="explore-meta">
            <p role="status">
              {feed.isFetching && !feed.isFetchingNextPage
                ? t("filters.refreshing")
                : total !== undefined
                  ? t(preview ? "preview.count" : "events.count", { count: total })
                  : ""}
              {map && total !== undefined ? ` · ${t("explore.onMap", { count: map.located_count })}` : ""}
            </p>
            <div className="explore-meta__actions">
              {filtered && (
                <BaseButton className="link-button" onClick={clearFilters}>
                  {t("filters.reset")}
                </BaseButton>
              )}
              <BaseButton className="link-button explore-meta__map" aria-expanded={mapOpen} onClick={() => setMapOpen(!mapOpen)}>
                <Icon name="map" size={16} />
                {t(mapOpen ? "explore.hideMap" : "explore.showMap")}
              </BaseButton>
            </div>
          </div>

          <div className="explore-map explore-map--inline" data-open={mapOpen || undefined} data-full={mapFull || undefined}>
            <MapPanel points={invalid ? [] : points} activeId={activeId} focusId={openId ?? pinnedId} followId={followId} onSelect={selectFromMap} truncated={Boolean(map?.truncated)} />
            <BaseButton
              className="icon-button map-full-toggle"
              aria-label={t(mapFull ? "map.full.close" : "map.full.open")}
              onClick={() => setMapFull(!mapFull)}
            >
              <Icon name={mapFull ? "close" : "expand"} size={18} />
            </BaseButton>
            {peekId && (
              <MapPeek
                key={peekId}
                id={peekId}
                preview={preview}
                known={items.find((item) => item.id === peekId)}
                onOpen={() => {
                  const id = peekId;
                  setPeekId(null);
                  setMapFull(false);
                  openRecord(id);
                }}
                onClose={() => setPeekId(null)}
              />
            )}
          </div>

          {pinnedId && !items.some((item) => item.id === pinnedId) && (
            <div id="pinned-event" className="feed feed--pinned">
              <PinnedCard
                id={pinnedId}
                from={pinnedFrom}
                preview={preview}
                onClose={() => {
                  setPinnedId(null);
                  if (openId === pinnedId) show(null);
                }}
              />
            </div>
          )}

          {feed.error && !feed.data ? (
            <div className="explore-state" role="alert">
              <Icon name="alert" size={22} />
              <p>{t("events.loadError")}</p>
              <BaseButton className="pill-button" onClick={() => void feed.refetch()}>
                {t("ui.retry")}
              </BaseButton>
            </div>
          ) : !feed.data && !invalid ? (
            <ol className="feed" aria-busy="true" aria-label={t("events.loading")}>
              {[0, 1, 2].map((index) => (
                <li key={index} className="card card--skeleton" />
              ))}
            </ol>
          ) : items.length === 0 ? (
            <div className="explore-state">
              <Icon name="search" size={22} />
              <h2>{t(filtered ? "explore.noMatch" : preview ? "preview.empty.title" : "events.empty.title")}</h2>
              <p>{t(filtered ? "explore.noMatchBody" : preview ? "preview.empty.body" : "events.empty.body")}</p>
              {filtered ? (
                <BaseButton className="pill-button" onClick={clearFilters}>
                  {t("filters.reset")}
                </BaseButton>
              ) : (
                !preview && (
                  <div className="explore-state__actions">
                    <Link to="/about" className="pill-button">
                      <Icon name="info" size={16} />
                      {t("events.empty.about")}
                    </Link>
                    <a className="pill-button" href="https://map.sosmediterranee.org/" target="_blank" rel="noreferrer">
                      {t("events.empty.sosMap")}
                    </a>
                  </div>
                )
              )}
            </div>
          ) : view === "logbook" ? (
            <Logbook
              items={items}
              preview={preview}
              openId={openId}
              hasMore={Boolean(feed.hasNextPage)}
              period={Boolean(start || end)}
              onToggle={(id) => {
                setPinnedId(null);
                show(openId === id ? null : id);
              }}
              onRead={setReadId}
            />
          ) : (
            <ol className="feed" aria-label={t(preview ? "preview.heading" : "events.heading")}>
              {items.map((item) => (
                <EventCard
                  key={item.id}
                  item={item}
                  preview={preview}
                  open={openId === item.id}
                  onHover={(hovered) => setHoverId(hovered ? item.id : null)}
                  onToggle={() => {
                    setPinnedId(null);
                    show(openId === item.id ? null : item.id);
                  }}
                />
              ))}
            </ol>
          )}
          {/* A failed "More" or refresh keeps the cards already loaded (frontend audit). */}
          {feed.error && feed.data && (
            <p className="explore-state__inline" role="alert">
              {t("events.loadError")}{" "}
              <BaseButton className="link-button" onClick={() => void (feed.isFetchNextPageError ? feed.fetchNextPage() : feed.refetch())}>
                {t("ui.retry")}
              </BaseButton>
            </p>
          )}
          {feed.hasNextPage && (
            <BaseButton className="pill-button feed-more" disabled={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>
              {feed.isFetchingNextPage ? t("events.loading") : t("explore.more")}
            </BaseButton>
          )}

          <footer className="explore-footer">
            <p>{t("app.footer.counts")}</p>
            <p>{t("app.context")}</p>
            <a href="https://map.sosmediterranee.org/" target="_blank" rel="noreferrer">
              {t("app.footer.sosMap")}
            </a>
          </footer>
        </section>

        <aside className="explore-map explore-map--side" aria-label={t("map.label")}>
          {/* On wide screens the timeline floats over the bottom of the map, as in the chosen mock-up. */}
          {view === "timeline" && renderTimeline("timeline--overlay", setOverlay)}
          <MapPanel
            points={invalid ? [] : points}
            activeId={activeId}
            focusId={openId ?? pinnedId}
            followId={followId}
            onSelect={selectFromMap}
            truncated={Boolean(map?.truncated)}
            insetBottom={view === "timeline" ? overlayHeight : 0}
          />
        </aside>
      </div>
    </div>
  );
}

function MapPanel({
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
  return (
    <div className="map-card">
      <Suspense fallback={<div className="map-card__loading">{t("map.loading")}</div>}>
        <EventMap points={points} onSelect={onSelect} activeId={activeId} focusId={focusId} followId={followId} insetBottom={insetBottom} />
      </Suspense>
      {truncated && <p className="map-card__note">{t("map.truncated")}</p>}
    </div>
  );
}

// Short labels for the card badge; the full sentence stays in the opened record.
function statusKey(status: Status): Key {
  return `explore.status.${status}` as Key;
}

function EventCard({
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

function PinnedCard({ id, from, preview, onClose }: { id: string; from: "link" | "map"; preview: boolean; onClose: () => void }) {
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

/** Smooth scrolling unless the reader asked the system to reduce motion. */
function motion(): ScrollBehavior {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/** A control reached with the keyboard in a strip that scrolls sideways is brought out from
 * under the edge fade (acceptance of 25 October 2026, D-B). */
function revealFocused(event: FocusEvent<HTMLElement>) {
  event.target.scrollIntoView?.({ block: "nearest", inline: "nearest" });
}

/** Record ids are UUIDs; anything else in the address is ignored rather than requested. */
function eventParam(value: string | null) {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value.toLowerCase() : null;
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
