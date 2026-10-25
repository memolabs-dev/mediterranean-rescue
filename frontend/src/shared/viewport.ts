import { useSyncExternalStore } from "react";

// Mirror explore.css exactly: only one of the phone or desktop maps must exist.
// CSS display:none alone still creates a WebGL map and a renderer worker.
const query = "(min-width: 960px)";
function current() {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.(query).matches);
}
function subscribe(change: () => void) {
  if (typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(query);
  media.addEventListener("change", change);
  return () => media.removeEventListener("change", change);
}
export function useDesktopViewport() {
  return useSyncExternalStore(subscribe, current, () => false);
}
