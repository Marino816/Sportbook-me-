/**
 * SB-Me Mobile API client.
 * Reuses existing backend API endpoints. JWT stored in SecureStore.
 */

import * as SecureStore from "expo-secure-store";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";
const TOKEN_KEY = "sportbook_me_token";

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ──
export async function login(email: string, password: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ email: email, password: password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  await setToken(data.data.access_token);
  return data.data;
}

export async function register(email: string, password: string) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return apiFetch("/auth/me");
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
  locked?: string[];
  excluded?: string[];
}) {
  return apiFetch("/builder/lineups", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ── Mission Control ──
export async function getMissionControl() {
  return apiFetch("/mission-control");
}