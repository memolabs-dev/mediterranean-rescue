// Onboarding progress is only a browser convenience. Real decisions remain on the server.
// Never reuse the old, unscoped keys: on a shared computer they belong to an unknown user.
const KEYS = {
  intro: "intro",
  practice: "practice",
  publishGuide: "publish-guide",
} as const;

export type JourneyKey = keyof typeof KEYS;

// Stable, low-collision namespace without putting a volunteer's username or email in storage.
// This is an identifier, NOT a secret or an authentication mechanism.
export function journeyStorageKey(key: JourneyKey, username: string): string {
  const encoded = new TextEncoder().encode(username);
  let hash = 0xcbf29ce484222325n;
  for (const byte of encoded) {
    hash = BigInt.asUintN(64, (hash ^ BigInt(byte)) * 0x100000001b3n);
  }
  return `team-journey-v2:${hash.toString(16).padStart(16, "0")}:${KEYS[key]}`;
}

export function journeyDone(key: JourneyKey, username: string): boolean {
  if (!username) return false;
  try {
    return window.localStorage.getItem(journeyStorageKey(key, username)) === "1";
  } catch {
    return false;
  }
}

export function markJourney(key: JourneyKey, username: string): void {
  if (!username) return;
  try {
    window.localStorage.setItem(journeyStorageKey(key, username), "1");
  } catch {
    // Storage disabled: replay onboarding next visit rather than marking another user done.
  }
}
