import { useEffect, useState } from "react";

export function useDebounced<T>(value: T, delay: number) {
  const [current, setCurrent] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setCurrent(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return current;
}

/** Height of an element, kept current while it resizes; 0 when there is none. */
export function useHeight(element: HTMLElement | null) {
  const [height, setHeight] = useState(0);
  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setHeight(Math.round(entry?.borderBoxSize[0]?.blockSize ?? element.offsetHeight)));
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return element ? height : 0;
}

