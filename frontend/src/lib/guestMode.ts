/** Guest browsing session — survives in-app navigation without ?guest=true on every URL. */

import { GUEST_ENABLED } from "./api";

const STORAGE_KEY = "mathbird:guest";

export function isGuestMode(): boolean {
  if (!GUEST_ENABLED) return false;
  try {
    return sessionStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function enterGuestMode(): void {
  if (!GUEST_ENABLED) return;
  try {
    sessionStorage.setItem(STORAGE_KEY, "true");
  } catch {
    // Private browsing may block storage; use ?guest=true on the URL instead.
  }
}

export function exitGuestMode(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

/** Enter guest mode when `?guest=true` is present on the current URL. */
export function syncGuestModeFromSearchParams(params: URLSearchParams): void {
  if (GUEST_ENABLED && params.get("guest") === "true") {
    enterGuestMode();
  }
}
