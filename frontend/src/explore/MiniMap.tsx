import { MED_BOUNDS, MED_LAND, MED_SCALE, MED_VIEWBOX } from "../shared/medOutline";

/** Where a point falls on the central Mediterranean locator, or null outside it. */
function place(longitude: number, latitude: number) {
  const { west, east, south, north } = MED_BOUNDS;
  if (longitude < west || longitude > east || latitude < south || latitude > north) return null;
  return { x: (longitude - west) * MED_SCALE, y: north - latitude };
}

// A single shared definition saves repeating the same ~10 KB path on each event card.
// Keep the definition inside Explore, which owns all MiniMap instances, so SVG <use>
// resolves within the same document on Safari and Chromium.
const LAND_ID = "med-rescue-mini-land";

export function MiniMapDefinitions() {
  return (
    <svg className="mini-map-definitions" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <path id={LAND_ID} d={MED_LAND} />
      </defs>
    </svg>
  );
}

// A static locator drawn from the same coastline as the map: no WebGL, cheap enough for every card.
export function MiniMap({
  position,
  label,
  unknownLabel,
}: {
  position: { longitude: number; latitude: number } | null;
  label: string;
  /** Written over the map when there is no point to show, so an empty map is never a puzzle. */
  unknownLabel?: string;
}) {
  const point = position ? place(position.longitude, position.latitude) : null;
  return (
    <span className={`mini-map-wrap${point ? "" : " mini-map-wrap--unknown"}`}>
      <svg className="mini-map" viewBox={MED_VIEWBOX} role="img" aria-label={label} preserveAspectRatio="xMidYMid slice">
        <use className="mini-map__land" href={"#" + LAND_ID} />
        {point && (
          <>
            <circle className="mini-map__halo" cx={point.x} cy={point.y} r={1.4} />
            <circle className="mini-map__dot" cx={point.x} cy={point.y} r={0.55} />
          </>
        )}
      </svg>
      {!point && unknownLabel && (
        <span className="mini-map__unknown" aria-hidden="true">
          {unknownLabel}
        </span>
      )}
    </span>
  );
}
