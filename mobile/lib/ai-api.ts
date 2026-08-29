/**
 * SB ME AI Model — Mobile API client extension.
 * Uses the canonical backend endpoint POST /api/ai/chat (same as web).
 */

import { getApiUrl, getToken } from "./api";

export interface AIPreferences {
  preferred_sport: string;
  preferred_contest: string;
  risk_tolerance: string;
  salary_utilization: string;
}

export interface AIChatContext {
  sport?: string | null;
  platform?: string | null;
  slate_id?: number | null;
  slate_name?: string | null;
  slate_start_time?: string | null;
  slate_status?: string | null;
  selected_players?: { name: string; player_id?: string | null }[];
  locked_players?: { name: string; player_id?: string | null }[];
  excluded_players?: { name: string; player_id?: string | null }[];
  requested_metrics?: string[];
  requested_action?: string | null;
  contest_type?: string | null;
  salary_cap?: number | null;
}

export interface AIMessage {
  role: "user" | "assistant";
  content: string;
  modules?: string[];
  confidence?: number;
  freshness?: string;
  timestamp?: string;
  conversation_id?: string;
  context?: AIChatContext;
  suggested_actions?: { id: string; label: string; prompt?: string; href?: string }[];
}

/**
 * Send a chat message to the SB ME AI assistant.
 * The backend returns { conversation_id, content, tools_used, context, ... }.
 */
export async function sendAIChat(
  message: string,
  conversationId?: string,
  history?: { role: string; content: string }[],
  context?: AIChatContext,
): Promise<AIMessage> {
  const token = await getToken();
  const res = await fetch(`${getApiUrl()}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      history: history || [],
      context: context || {},
      sport: context?.sport || undefined,
      platform: context?.platform || undefined,
      slate_id: context?.slate_id || undefined,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `AI service unavailable (${res.status})`);
  }
  const data = await res.json();
  return {
    role: "assistant",
    content: data.content || "I processed your request.",
    conversation_id: data.conversation_id,
    context: data.context,
    suggested_actions: data.suggested_actions,
  };
}

// ── Strategy Mode (still backed by /assistant/strategy-mode) ──
export async function setStrategyMode(mode: string) {
  const token = await getToken();
  const res = await fetch(`${getApiUrl()}/assistant/strategy-mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ mode }),
  });
  return res.json();
}
