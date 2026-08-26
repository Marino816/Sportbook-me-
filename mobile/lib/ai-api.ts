/**
 * SB ME AI Model — Mobile API client extension.
 * Uses the canonical backend endpoint POST /api/ai/chat (same as web).
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

/**
 * Send a chat message to the SB ME AI assistant.
 * The backend returns { conversation_id, content, tools_used, model, ... }.
 */
export async function sendAIChat(message: string, conversationId?: string): Promise<AIMessage> {
  const token = await getToken();
  const res = await fetch(`${API_URL}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `AI service unavailable (${res.status})`);
  }
  const data = await res.json();
  return { role: "assistant", content: data.content || "I processed your request." };
}

// ── Strategy Mode (still backed by /assistant/strategy-mode) ──
export async function setStrategyMode(mode: string) {
  const token = await getToken();
  const res = await fetch(`${API_URL}/assistant/strategy-mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ mode }),
  });
  return res.json();
}
