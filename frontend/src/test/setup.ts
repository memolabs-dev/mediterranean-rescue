import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { resetCsrfToken } from "../api/client";

// Node 26 can expose a nonfunctional Web Storage global to jsdom. Keep tests using a
// per-environment, in-memory Storage when the browser-provided one is unavailable.
if (typeof window !== "undefined") {
  let available = false;
  try {
    available = Boolean(window.localStorage);
  } catch {
    // Opaque jsdom origins may throw when accessing storage.
  }
  if (!available) {
    const values = new Map<string, string>();
    const storage: Storage = {
      get length() { return values.size; },
      clear: () => values.clear(),
      getItem: (key) => values.get(key) ?? null,
      key: (index) => [...values.keys()][index] ?? null,
      removeItem: (key) => { values.delete(key); },
      setItem: (key, value) => { values.set(key, String(value)); },
    };
    Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  }
}

afterEach(() => {
  cleanup();
  // The cached CSRF token must not leak from one test to the next.
  resetCsrfToken();
});
