/**
 * Session auth via Google OAuth + HttpOnly cookie.
 *
 * Guest mode: when GUEST_ENABLED is set in the build env (VITE_GUEST_ENABLED),
 * the login page shows a "Try as guest" button. Guest sessions skip OAuth
 * entirely — the token route issues an ephemeral identity.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const GUEST_ENABLED = import.meta.env.VITE_GUEST_ENABLED === "true";

export interface User {
  id: string;
  email: string;
  name: string;
}

export function googleLoginUrl(): string {
  return `${API_BASE}/api/auth/google`;
}

export async function getMe(): Promise<User | null> {
  const res = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json() as Promise<User>;
}

export async function logout(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(await res.text());
  }
}
