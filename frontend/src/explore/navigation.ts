import type { FocusEvent } from "react";

/** Smooth scrolling unless the reader asked the system to reduce motion. */
export function motion(): ScrollBehavior {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/** A control reached with the keyboard in a strip that scrolls sideways is brought out from
 * under the edge fade (acceptance of 25 October 2026, D-B). */
export function revealFocused(event: FocusEvent<HTMLElement>) {
  event.target.scrollIntoView?.({ block: "nearest", inline: "nearest" });
}

/** Record ids are UUIDs; anything else in the address is ignored rather than requested. */
export function eventParam(value: string | null) {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value.toLowerCase() : null;
}

