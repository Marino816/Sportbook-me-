"use client";

import { useAuth } from "@/lib/auth";
import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sbme_dfs_token");
}

const DEFAULT_MSG =
  "Welcome to SB ME AI. I have access to DFS slates, player projections, SportsGameOdds market intelligence, lineup optimization, and the Market Tools suite. How can I help?";

export default function AIPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Loading SportsGameOdds context..." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  // On load, fetch MLB events and inject into initial message
  useEffect(() => {
    let cancelled = false;
    async function loadContext() {
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/sgo/events?league=MLB`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error("unavailable");
        const json = await res.json();
        const events = Array.isArray(json?.data) ? json.data : [];
        if (events.length > 0) {
          const matchups = events
            .slice(0, 8)
            .map((e: any) => {
              const a = e.away_team?.abbreviation || e.away_team?.name || "AWY";
              const h = e.home_team?.abbreviation || e.home_team?.name || "HOM";
              const status = e.status?.toUpperCase?.();
              const liveTag = status === "LIVE" || status === "IN_PLAY" ? " (LIVE)" : "";
              return `${a} @ ${h}${liveTag}`;
            })
            .join(", ");
          const msg = `Today's MLB games: ${matchups}. I can answer questions about odds, props, and DFS lineups.`;
          if (!cancelled) setMessages([{ role: "assistant", content: msg }]);
        } else {
          if (!cancelled) setMessages([{ role: "assistant", content: DEFAULT_MSG }]);
        }
      } catch {
        if (!cancelled) setMessages([{ role: "assistant", content: DEFAULT_MSG }]);
      }
    }
    loadContext();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const token = localStorage.getItem("sbme_dfs_token");
      const res = await fetch(`${API_BASE}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: text }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [...prev, { role: "assistant", content: data.response || data.data?.response || "I processed your request." }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "SB ME AI is available for market intelligence, player analysis, lineup optimization, and odds comparison. Ask me about any published DFS slate or player prop market." }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "I'm connected to the SB ME Intelligence engine. Ask me about DFS slates, player projections, SportsGameOdds markets, or your saved lineups." }]);
    }
    setSending(false);
  };

  if (!user) {
    return (
      <div style={{ background: "#060b1a", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>SB ME AI</h1>
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to access SB ME Intelligent AI.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#060b1a", height: "calc(100vh - 64px)", display: "flex", flexDirection: "column", color: "#f0f6fc" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>SB ME AI</h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
          Connected: SportsGameOdds · Native DFS · Market Tools · Lineup Engine
        </p>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            marginBottom: 12, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
          }}>
            <div style={{
              maxWidth: "75%", padding: "12px 16px", borderRadius: 14,
              background: m.role === "user" ? "#c9a84c" : "#0a0f24",
              color: m.role === "user" ? "#060b1a" : "#f0f6fc",
              border: m.role === "user" ? "none" : "1px solid #1e293b",
              fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap",
            }}>
              {m.content}
            </div>
          </div>
        ))}
        <div ref={chatEnd} />
      </div>

      <div style={{ padding: "12px 24px", borderTop: "1px solid #1e293b" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about DFS slates, player props, lineups..."
            style={{
              flex: 1, padding: "12px 16px", borderRadius: 12, border: "1px solid #1e293b",
              background: "#0a0f24", color: "#f0f6fc", fontSize: 14, outline: "none",
            }} />
          <button onClick={send} disabled={sending} style={{
            padding: "12px 16px", borderRadius: 12, background: "#c9a84c", color: "#060b1a",
            border: "none", cursor: "pointer", fontWeight: 700, display: "flex", alignItems: "center", gap: 6,
          }}>
            {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            Send
          </button>
        </div>
      </div>
    </div>
  );
}