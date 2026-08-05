/**
 * Phase 7 SB-Me Intelligence API client.
 *
 * Typed request/response contracts for Scout, Analyst, Builder, Coach,
 * Mission Control, and AI Assistant endpoints.
 */
import { getStoredToken } from "./api";

const TOKEN_KEY = "sbme_dfs_token";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${base}${url}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    if (res.status === 403) throw new Error("Subscription required");
    if (res.status === 429) throw new Error("Rate limit exceeded");
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

// ── Scout ──────────────────────────────────────────────────

export interface ScoutEvent {
  event_id: string;
  event_type: string;
  severity: string;
  sport: string;
  timestamp: string;
}

export async function getScoutEvents(limit = 20): Promise<{ data: { events: ScoutEvent[]; total: number } }> {
  return apiFetch(`/scout/events?limit=${limit}`);
}

export async function getScoutProviders(): Promise<{ data: { providers: any[] } }> {
  return apiFetch("/scout/providers");
}

export async function getScoutFreshness(): Promise<{ data: any }> {
  return apiFetch("/scout/freshness");
}

// ── Analyst ────────────────────────────────────────────────

export async function getPlayerAnalysis(playerId: number): Promise<{ data: any }> {
  return apiFetch(`/analyst/player/${playerId}`);
}

export async function getSlateAnalysis(slateId: number): Promise<{ data: any }> {
  return apiFetch(`/analyst/slate/${slateId}`);
}

export async function getTopEdges(slateId: number): Promise<{ data: any }> {
  return apiFetch(`/analyst/top-edges?slate_id=${slateId}`);
}

export async function getProjectionChange(entityId: number): Promise<{ data: any }> {
  return apiFetch(`/analyst/projection-change/${entityId}`);
}

// ── Builder ────────────────────────────────────────────────

export interface BuilderLineupRequest {
  slate_id: number;
  platform?: string;
  sport?: string;
  strategy?: string;
  lineup_count?: number;
  locked_player_ids?: number[];
  excluded_player_ids?: number[];
  randomness?: number;
}

export async function buildLineups(req: BuilderLineupRequest): Promise<{ data: any }> {
  return apiFetch("/builder/lineups", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function validateLineup(req: BuilderLineupRequest): Promise<{ data: any }> {
  return apiFetch("/builder/validate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function buildPortfolio(req: BuilderLineupRequest): Promise<{ data: any }> {
  return apiFetch("/builder/portfolios", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getBuilderStrategies(): Promise<{ data: { strategies: any[] } }> {
  return apiFetch("/builder/strategies");
}

// ── Coach ──────────────────────────────────────────────────

export async function getCoachPerformance(): Promise<{ data: any }> {
  return apiFetch("/coach/performance");
}

export async function getCoachFindings(): Promise<{ data: any }> {
  return apiFetch("/coach/findings");
}

export async function getCoachRecommendations(): Promise<{ data: any }> {
  return apiFetch("/coach/recommendations");
}

export async function getCoachStrategies(): Promise<{ data: any }> {
  return apiFetch("/coach/strategies");
}

// ── Mission Control ────────────────────────────────────────

export async function getMissionControl(): Promise<{ data: { widgets: Record<string, any>; widget_count: number; tier: string } }> {
  return apiFetch("/mission-control");
}

export async function getDailyBriefing(): Promise<{ data: any }> {
  return apiFetch("/mission-control/briefing");
}

export async function getSystemHealth(): Promise<{ data: any }> {
  return apiFetch("/mission-control/system-health");
}

export async function saveMCPreferences(prefs: Record<string, any>): Promise<{ data: any }> {
  return apiFetch("/mission-control/preferences", {
    method: "POST",
    body: JSON.stringify(prefs),
  });
}

// ── AI Assistant ───────────────────────────────────────────

export async function sendAssistantChat(message: string, conversationId?: string): Promise<{ data: { conversation_id: string; response: any } }> {
  return apiFetch("/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

export async function getStrategyModes(): Promise<{ data: { modes: any[] } }> {
  return apiFetch("/assistant/strategy-modes");
}

export async function setStrategyMode(mode: string): Promise<{ data: any }> {
  return apiFetch("/assistant/strategy-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function getWarRoom(): Promise<{ data: any }> {
  return apiFetch("/assistant/war-room");
}

// ── AI Engine ──────────────────────────────────────────────

export async function getModelStatus(): Promise<{ data: any }> {
  return apiFetch("/ai/model-status");
}

export async function getAIProjections(slateId: number, sport = "nba"): Promise<{ data: any }> {
  return apiFetch(`/ai/projections?slate_id=${slateId}&sport=${sport}`);
}

export async function getPlayerExplanation(playerId: number): Promise<{ data: any }> {
  return apiFetch(`/ai/players/${playerId}/explanation`);
}