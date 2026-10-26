import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Map as LibreMap, NavigationControl, setWorkerUrl, type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { MapPoints as Points } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

setWorkerUrl(workerUrl);

function supportsWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    // Release the probe context: browsers cap the number of live WebGL contexts.
    context?.getExtension("WEBGL_lose_context")?.loseContext();
    return context !== null;
  } catch {
    return false;
  }
}

function asFeatures(points: Points) {
  return {
    type: "FeatureCollection" as const,
    features: points.map((p) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [p.longitude, p.latitude] },
      properties: { id: p.id, kind: p.kind },
    })),
  };
}

export function EventMap({
  points,
  onSelect,
  activeId = null,
  focusId = null,
  followId = null,
  insetBottom = 0,
}: {
  points: Points;
  onSelect: (id: string) => void;
  /** The event open in the list: ringed on the map and brought into view. */
  activeId?: string | null;
  /** The event to bring into view when it is off screen (an opened one, not a hovered one). */
  focusId?: string | null;
  /** The event being read in the logbook: the map pans to it only when it is off screen. */
  followId?: string | null;
  /** Height in pixels covered at the bottom of the map by an overlay. */
  insetBottom?: number;
}) {
  const { t } = useI18n();
  const element = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<LibreMap | null>(null);
  // Checked once before the map exists, so a missing WebGL never needs a state update in an effect.
  const [failed, setFailed] = useState(() => !supportsWebGL());
  // A non-fatal map error (a tile or source fetch) keeps the map and only shows the notice.
  const [degraded, setDegraded] = useState(false);
  // Map listeners always call the latest callbacks without re-creating the map.
  const select = useEffectEvent((id: string) => onSelect(id));
  const fail = useEffectEvent(() => setFailed(true));
  const degrade = useEffectEvent(() => setDegraded(true));
  // Read once at creation: changing language must not rebuild the map and lose the view.
  const attribution = useEffectEvent(() => t("map.attribution"));
  // The map's own buttons in the reader's language (MapLibre's locale option).
  const controls = useEffectEvent(() => ({
    "Map.Title": t("map.ui.title"),
    "NavigationControl.ZoomIn": t("map.ui.zoomIn"),
    "NavigationControl.ZoomOut": t("map.ui.zoomOut"),
    "AttributionControl.ToggleAttribution": t("map.ui.attribution"),
  }));

  useEffect(() => {
    if (failed || !element.current) return;
    // CSS design tokens are also the single source for MapLibre's canvas palette.
    const design = getComputedStyle(element.current);
    const color = (name: string) => design.getPropertyValue(name).trim();
    let instance: LibreMap;
    try {
      instance = new LibreMap({
        container: element.current,
        center: [15, 35.5],
        zoom: 4,
        maxBounds: [
          [-15, 20],
          [50, 55],
        ],
        style: {
          version: 8,
          sources: { land: { type: "geojson", data: "/land.geojson" } },
          layers: [
            { id: "water", type: "background", paint: { "background-color": color("--sos-water") } },
            { id: "land", type: "fill", source: "land", paint: { "fill-color": color("--sos-land") } },
            { id: "coast", type: "line", source: "land", paint: { "line-color": color("--sos-coast"), "line-width": 0.7 } },
          ],
        },
        attributionControl: { customAttribution: attribution() },
        locale: controls(),
      });
    } catch {
      // The external map failed to start (WebGL lost, driver refusal): report it like any
      // other map event, outside the effect body, and keep the list usable.
      queueMicrotask(fail);
      return;
    }
    instance.addControl(new NavigationControl({ showCompass: false }), "top-left");
    let loaded = false;
    instance.on("load", () => {
      loaded = true;
      instance.addSource("events", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterMaxZoom: 8,
        clusterRadius: 35,
      });
      instance.addLayer({
        id: "clusters",
        type: "circle",
        source: "events",
        filter: ["has", "point_count"],
        // Larger groups read larger, in three steps.
        paint: {
          "circle-color": color("--sos-navy"),
          "circle-opacity": 0.92,
          "circle-radius": ["step", ["get", "point_count"], 13, 10, 17, 50, 22],
          "circle-stroke-color": color("--sos-white"),
          "circle-stroke-width": 2,
        },
      });
      instance.addLayer({
        id: "events",
        type: "circle",
        source: "events",
        filter: ["!", ["has", "point_count"]],
        // Each kind keeps its colour from the filter chips; orange-red is kept for selection.
        paint: {
          "circle-color": [
            "match",
            ["get", "kind"],
            "transfer", color("--sos-kind-transfer"),
            "medevac", color("--sos-kind-medevac"),
            "incident", color("--sos-kind-incident"),
            "shipwreck", color("--sos-kind-shipwreck"),
            "dead_missing", color("--sos-kind-dead-missing"),
            color("--sos-kind-rescue"),
          ],
          "circle-radius": 6,
          "circle-stroke-color": color("--sos-white"),
          "circle-stroke-width": 2,
        },
      });
      instance.addSource("active", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      // The hovered or open event sits above every group: a halo and a solid orange point.
      instance.addLayer({
        id: "active-halo",
        type: "circle",
        source: "active",
        paint: { "circle-color": color("--sos-selected-map-halo"), "circle-radius": 22, "circle-blur": 0.15 },
      });
      instance.addLayer({
        id: "active",
        type: "circle",
        source: "active",
        paint: { "circle-color": color("--sos-orange"), "circle-radius": 9, "circle-stroke-color": color("--sos-white"), "circle-stroke-width": 3 },
      });
      instance.on("click", "events", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (typeof id === "string") select(id);
      });
      instance.on("click", "clusters", (e) => {
        const feature = e.features?.[0];
        if (feature?.geometry.type === "Point") {
          const [lon, lat] = feature.geometry.coordinates;
          const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
          instance.easeTo({ center: [lon ?? 15, lat ?? 35], zoom: Math.min(instance.getZoom() + 2, 10), duration: reduce ? 0 : 500 });
        }
      });
      instance.on("mouseenter", "events", () => {
        instance.getCanvas().style.cursor = "pointer";
      });
      instance.on("mouseleave", "events", () => {
        instance.getCanvas().style.cursor = "";
      });
      setMap(instance);
    });
    // Before load the map cannot work (style or WebGL failure); after load it degrades only.
    instance.on("error", () => (loaded ? degrade() : fail()));
    return () => {
      setMap(null);
      instance.remove();
    };
  }, [failed]);

  // Space covered by something drawn over the bottom of the map (the timeline on wide screens):
  // the camera centres and frames above it.
  useEffect(() => {
    map?.setPadding({ top: 0, right: 0, left: 0, bottom: insetBottom });
  }, [map, insetBottom]);

  // Points are pushed to the loaded map whenever they change; the first non-empty set frames the view.
  const framed = useRef(false);
  useEffect(() => {
    if (!map) return;
    map.getSource<GeoJSONSource>("events")?.setData(asFeatures(points));
    if (framed.current || points.length === 0) return;
    framed.current = true;
    const lons = points.map((point) => point.longitude);
    const lats = points.map((point) => point.latitude);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      // Capped so coasts stay recognisable with the simplified land layer.
      { padding: 48, maxZoom: 5, duration: 0 },
    );
  }, [map, points]);

  // The open or hovered event is ringed wherever it is.
  useEffect(() => {
    if (!map) return;
    map.getSource<GeoJSONSource>("active")?.setData(asFeatures(points.filter((point) => point.id === activeId)));
  }, [map, points, activeId]);

  // The camera moves only when the event to show changes, never because the points were refreshed,
  // so a pan by the reader is not undone. Dragging the map stops following the logbook until an
  // event is opened again.
  const shown = useRef<{ focus: string | null; follow: string | null }>({ focus: null, follow: null });
  const paused = useRef(false);
  useEffect(() => {
    if (!map) return;
    const pause = () => {
      paused.current = true;
    };
    map.on("dragstart", pause);
    return () => {
      map.off("dragstart", pause);
    };
  }, [map]);
  useEffect(() => {
    if (!map) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (focusId !== shown.current.focus) {
      if (focusId) {
        // An opened event always travels to the centre, so the card and its place read together.
        const point = points.find((item) => item.id === focusId);
        if (!point) return; // not loaded yet: try again when the points arrive
        shown.current.focus = focusId;
        paused.current = false;
        map.easeTo({ center: [point.longitude, point.latitude], duration: reduce ? 0 : 700 });
        return;
      }
      shown.current.focus = null;
    }
    if (focusId || paused.current || !followId || followId === shown.current.follow) return;
    const point = points.find((item) => item.id === followId);
    if (!point) return;
    shown.current.follow = followId;
    // The entry being read moves the map only when its point is off screen.
    if (!map.getBounds().contains([point.longitude, point.latitude])) {
      map.easeTo({ center: [point.longitude, point.latitude], duration: reduce ? 0 : 500 });
    }
  }, [map, points, focusId, followId]);

  return (
    <div className="map-wrap">
      <div ref={element} className="map" role="region" aria-label={t("map.label")} />
      {(failed || degraded) && (
        <p role="status" className="map-notice">
          {t("map.unavailable")}
        </p>
      )}
      <span className="map-caption">{t("map.caption")}</span>
    </div>
  );
}
