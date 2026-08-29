/**
 * Canonical Sportbook Me mobile API client (Expo Router).
 *
 * Active app entry is expo-router (`mobile/app/**`).
 * Do not import the abandoned App.tsx / src prototype for runtime behavior.
 *
 * Base URL: EXPO_PUBLIC_API_URL, else production Railway /api.
 */

import * as SecureStore from "expo-secure-store";

export const DEFAULT_API_URL = "https://sportbook-me-production.up.railway.app/api";
const TOKEN_KEY = "sportbook_me_token";

export function getApiUrl(): string {
  const fromEnv = (process.env.EXPO_PUBLIC_API_URL || "").trim();
  return fromEnv || DEFAULT_API_URL;
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export type AuthUser = {
  id?: number;
  email?: string;
  username?: string | null;
  name?: string;
  role?: string;
  plan?: string;
  is_pro?: boolean;
  is_active?: boolean;
};

export function unwrapUser(body: unknown): AuthUser | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as Record<string, unknown>;
  const nested = raw.data;
  const src =
    nested && typeof nested === "object" && ("email" in (nested as object) || "id" in (nested as object))
      ? (nested as Record<string, unknown>)
      : raw;
  if (src.email == null && src.id == null) return null;
  return src as AuthUser;
}

export async function apiFetch<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiUrl()}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string; message?: string }).detail
      || (body as { message?: string }).message
      || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ──
export async function login(identifier: string, password: string) {
  const res = await fetch(`${getApiUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: identifier.trim(), password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string }).detail;
    throw new Error(typeof detail === "string" ? detail : "Invalid credentials");
  }
  const data = await res.json();
  if (!data?.access_token) throw new Error("Login failed");
  await setToken(data.access_token);
  return data;
}

export async function register(username: string, email: string, password: string) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

export async function getMe() {
  return apiFetch("/auth/me");
}

/**
 * Validate a stored JWT with GET /auth/me.
 * Missing or unauthorized tokens are cleared. Network failures keep the token
 * but do not establish a session.
 */
export async function restoreSession(): Promise<AuthUser | null> {
  const token = await getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${getApiUrl()}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) {
      await clearToken();
      return null;
    }
    if (!res.ok) return null;
    return unwrapUser(await res.json());
  } catch {
    return null;
  }
}

// ── Billing ──
export async function getSubscriptionStatus() {
  return apiFetch("/billing/status");
}

export async function createCheckout(plan: string) {
  return apiFetch("/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function openBillingPortal() {
  return apiFetch("/billing/portal");
}

// ── Builder ──
export async function buildLineups(params: {
  platform: string;
  strategy?: string;
  count?: number;
  slate_id?: number;
  locked?: string[];
  excluded?: string[];
}) {
  return apiFetch("/builder/lineups", {
    method: "POST",
    body: JSON.stringify({
      slate_id: params.slate_id || 1,
      platform: params.platform,
      strategy: params.strategy || "balanced",
      lineup_count: params.count || 1,
      locked_player_ids: params.locked || [],
      excluded_player_ids: params.excluded || [],
    }),
  });
}

// ── Mission Control ──
export async function getMissionControl() {
  return apiFetch("/mission-control");
}
