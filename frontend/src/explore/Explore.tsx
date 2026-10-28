import { Button as BaseButton } from "@base-ui/react/button";
import { useEffect, useRef, useState } from "react";
import { keepPreviousData } from "@tanstack/react-query";
import { api, type Kind } from "../api/client";
import { kinds } from "../filters";
import { useI18n } from "../i18n/I18nProvider";
import { changeQuery, Link, useLocation } from "../router";
import { useDesktopViewport } from "../shared/viewport";
import { Icon } from "../ui/Icon";
import { fromNewsSite, missionName } from "./Evidence";
import { kindLabel } from "./labels";
import { Logbook } from "./Logbook";
import { MapPeek } from "./MapPeek";
import { MiniMapDefinitions } from "./MiniMap";
import { PublicBar } from "./PublicBar";
import { Welcome } from "./Welcome";
import { Timeline } from "./Timeline";
import { EventCard, PinnedCard } from "./EventCards";
import { MapPanel } from "./MapPanel";
import { useDebounced, useHeight } from "./hooks";
import { eventParam, motion, revealFocused } from "./navigation";
import type { FeedItem, Status } from "./types";

const PAGE = 25;
const LOGBOOK_SOURCE = "sos-logbook";
// Three ways to read the same events.
type View = "feed" | "logbook" | "timeline";
const VIEWS: readonly { value: View; icon: "map" | "calendar" | "anchor" }[] = [
  { value: "feed", icon: "anchor" },
  { value: "logbook", icon: "calendar" },
  { value: "timeline", icon: "map" },
];
// The same reading screen for two audiences, never mixed: "public" shows only published events;
// "team" (inside the team space) shows the latest data received, with its review state.
export function Explore({ audience = "public" }: { audience?: "public" | "team" }) {
  const i18n = useI18n();
  const { t } = i18n;
  const preview = audience === "team";
  const desktop = useDesktopViewport();
  const { query } = useLocation();
  const requested = VIEWS.find((item) => item.value === query.get("view"));
  const view: View = requested?.value ?? "feed";

  const [text, setText] = useState("");
  const q = useDebounced(text.trim(), 300);
  const [kind, setKind] = useState<Kind | "">("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [periodOpen, setPeriodOpen] = useState(false);
  const periodButton = useRef<HTMLButtonElement>(null);
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

  // An intermediary can respond with HTML (e.g. a 502), leaving a missing API page.
  // Never let pagination crash the entire site in that situation.
  const page = (all: readonly unknown[], last: { has_next: boolean } | undefined) => (last?.has_next ? all.length * PAGE : undefined);
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
  const malformed = Boolean(feed.data?.pages.some((response) => !response));
  // Preserve previously loaded pages when an intermediary returns an invalid next page.
  const publicPages = (publicFeed.data?.pages ?? []).filter(Boolean);
  const previewPages = (previewFeed.data?.pages ?? []).filter(Boolean);
  const map = preview ? previewMap.data : publicMap.data;
  const items: FeedItem[] = preview
    ? previewPages.flatMap((p) =>
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
    : publicPages.flatMap((p) =>
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
      <MiniMapDefinitions />
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
                <BaseButton className="composer__clear" aria-label={t("ui.search.clear")} onClick={() => {
                      setText("");
                      resetView();
                    }}>
                  <Icon name="close" size={16} />
                </BaseButton>
              )}
            </label>
            <div className="chips" role="group" aria-label={t("filters.kind")} onFocus={revealFocused}>
              <BaseButton className="chip" aria-pressed={kind === ""} onClick={() => {
                  setKind("");
                  resetView();
                }}>
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
              <BaseButton ref={periodButton} className="chip chip--period" aria-pressed={Boolean(start || end)} aria-expanded={periodOpen} aria-controls="explore-date-range" onClick={() => setPeriodOpen(!periodOpen)}>
                <Icon name="calendar" size={15} />
                {start || end ? t("explore.periodSet", { from: start ? i18n.date(start) : "…", to: end ? i18n.date(end) : "…" }) : t("explore.period")}
              </BaseButton>
            </div>
            <div
              id="explore-date-range"
              className="composer__period"
              data-open={periodOpen || undefined}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.stopPropagation();
                  setPeriodOpen(false);
                  periodButton.current?.focus();
                }
              }}
            >
              <div className="composer__period-inner">
                <label>
                  {t("filters.from")}
                  <input type="date" value={start} max={end || undefined} onChange={(event) => {
                      setStart(event.target.value);
                      resetView();
                    }} />
                </label>
                <label>
                  {t("filters.to")}
                  <input type="date" value={end} min={start || undefined} onChange={(event) => {
                      setEnd(event.target.value);
                      resetView();
                    }} />
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
            {!desktop && mapOpen && (
              <MapPanel points={invalid ? [] : points} activeId={activeId} focusId={openId ?? pinnedId} followId={followId} onSelect={selectFromMap} truncated={Boolean(map?.truncated)} />
            )}
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

          {(feed.error || malformed) && (!feed.data || items.length === 0) ? (
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
          {(feed.error || malformed) && items.length > 0 && (
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
          {desktop && view === "timeline" && renderTimeline("timeline--overlay", setOverlay)}
          {desktop && (
            <MapPanel
              points={invalid ? [] : points}
              activeId={activeId}
              focusId={openId ?? pinnedId}
              followId={followId}
              onSelect={selectFromMap}
              truncated={Boolean(map?.truncated)}
              insetBottom={view === "timeline" ? overlayHeight : 0}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

