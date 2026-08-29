/**
 * Canonical Sportbook Me mobile API client (Expo Router).
 *
 * JWT storage is expo-secure-store ONLY (key: sportbook_me_token).
 * Do not persist credentials in AsyncStorage.
 *
 * Expo Go on iOS may drop Keychain items when the experience is force-closed.
 * That is an Expo Go container limitation, not a reason to weaken storage.
 * Re-test persistence in a later EAS development build.
 *
 * Base URL: EXPO_PUBLIC_API_URL, else production Railway /api.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

export const DEFAULT_API_URL = "https://sportbook-me-production.up.railway.app/api";
export const TOKEN_KEY = "sportbook_me_token";

const SECURE_OPTS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
};

function isDev(): boolean {
  return typeof __DEV__ !== "undefined" && __DEV__;
}

function authLog(event: string, extra: Record<string, unknown> = {}): void {
  if (!isDev()) return;
  console.log(`[sbme-auth] ${event}`, extra);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Drop any leftover JWT copy from a prior insecure fallback. Never read it back as auth. */
async function discardInsecureTokenCopy(): Promise<void> {
  try {
    await AsyncStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function getApiUrl(): string {
  const fromEnv = (process.env.EXPO_PUBLIC_API_URL || "").trim();
  return fromEnv || DEFAULT_API_URL;
}

export async function getToken(): Promise<string | null> {
  await discardInsecureTokenCopy();
  try {
    const fromSecure =
      (await SecureStore.getItemAsync(TOKEN_KEY)) ||
      (await SecureStore.getItemAsync(TOKEN_KEY, SECURE_OPTS));
    if (fromSecure) {
      authLog("token-read", { source: "secure-store", present: true });
      return fromSecure;
    }
  } catch (e) {
    authLog("token-read-secure-failed", { message: e instanceof Error ? e.message : "error" });
  }

  authLog("token-read", { source: "secure-store", present: false });
  return null;
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token, SECURE_OPTS);
  await discardInsecureTokenCopy();
  let secureOk = false;
  try {
    secureOk = !!(
      (await SecureStore.getItemAsync(TOKEN_KEY)) ||
      (await SecureStore.getItemAsync(TOKEN_KEY, SECURE_OPTS))
    );
  } catch {
    secureOk = false;
  }
  authLog("token-write", { securePersisted: secureOk });
  if (!secureOk) {
    throw new Error("Could not persist session");
  }
}

export async function clearToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    /* continue */
  }
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY, SECURE_OPTS);
  } catch {
    /* continue */
  }
  await discardInsecureTokenCopy();
  authLog("token-cleared", {});
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
  authLog("login-token-stored", { persisted: true });
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

export type SessionRestore =
  | { kind: "authenticated"; user: AuthUser }
  | { kind: "unauthenticated"; reason: "no_token" | "invalid" }
  | { kind: "transient" };

/**
 * Validate a stored JWT with GET /auth/me.
 * 401/403 clears the token. Transient failures keep the token.
 */
export async function restoreSession(): Promise<SessionRestore> {
  authLog("restore-start", {});
  let token = await getToken();
  if (!token) {
    for (let i = 0; i < 3; i++) {
      await delay(200);
      token = await getToken();
      if (token) break;
    }
  }
  if (!token) {
    authLog("restore-no-token", {});
    return { kind: "unauthenticated", reason: "no_token" };
  }

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(`${getApiUrl()}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      authLog("restore-me", { status: res.status, attempt });
      if (res.status === 401 || res.status === 403) {
        await clearToken();
        return { kind: "unauthenticated", reason: "invalid" };
      }
      if (!res.ok) {
        if (attempt < 3) {
          await delay(300);
          continue;
        }
        authLog("restore-transient", { status: res.status });
        return { kind: "transient" };
      }
      const user = unwrapUser(await res.json());
      authLog("restore-user", { ok: !!user, hasEmail: !!user?.email });
      if (user) return { kind: "authenticated", user };
      authLog("restore-transient", { reason: "unwrap" });
      return { kind: "transient" };
    } catch (e) {
      authLog("restore-me-error", { attempt, message: e instanceof Error ? e.message : "error" });
      if (attempt < 3) await delay(300);
    }
  }
  authLog("restore-transient", { reason: "network" });
  return { kind: "transient" };
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
