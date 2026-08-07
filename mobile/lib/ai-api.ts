/**
 * SBM Intelligent AI Model — Mobile API client extension.
 * Integrates with backend /assistant endpoints.
 */

import { getToken } from "./api";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";

export interface AIMessage {
  role: "user" | "assistant";
  content: string;
  modules?: string[];
  confidence?: number;
  freshness?: string;
  timestamp?: string;
}

export interface AIPreferences {
  preferred_sport?: string;
  preferred_contest?: "cash" | "gpp" | "single_entry" | "tournament";
  risk_tolerance?: "low" | "medium" | "high";
  favorite_stacks?: string[];
  salary_utilization?: "conservative" | "balanced" | "aggressive";
  last_lineup_id?: string;
  saved_player_pools?: string[];
}

// ── Core AI Chat ──
export async function sendAIChat(message: string, conversationId?: string): Promise<AIMessage> {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error(`AI service unavailable (${res.status})`);
  const data = await res.json();
  return data.data || data;
}

// ── Strategy Mode ──
export async function setStrategyMode(mode: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/strategy-mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ mode }),
  });
  return res.json();
}

// ── AI Lineup Builder ──
export async function buildAILineup(params: {
  platform: string;
  strategy: string;
  sport?: string;
  locked?: string[];
  excluded?: string[];
  preferences?: AIPreferences;
}) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/build-lineup`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Lineup build failed (${res.status})`);
  return res.json();
}

// ── AI Lineup Analysis ──
export async function analyzeLineup(lineupId: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/analyze-lineup`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ lineup_id: lineupId }),
  });
  return res.json();
}

// ── Player Comparison ──
export async function comparePlayers(player1: string, player2: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/compare-players`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ player1, player2 }),
  });
  return res.json();
}

// ── Slate Summary ──
export async function getSlateSummary(sport?: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/slate-summary`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  return res.json();
}