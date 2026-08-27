"use client";

import { useAuth } from "@/lib/auth";
import { useState, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
}

const WELCOME =
  "Welcome to SB ME AI. I can explain SB ME features and metrics, guide you around the product, and pull current slate data (salaries, SB Projection, Value, SB OWN%, Leverage, Optimal%) from live SB ME data. How can I help?";

export default function AIPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: WELCOME },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  const scrollToEnd = () => chatEnd.current?.scrollIntoView({ behavior: "smooth" });

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
        body: JSON.stringify({ message: text, page: "ai" }),
      });
      if (res.ok) {
        const data = await res.json();
        const content = data.content || data.response || data.data?.response || "I processed your request.";
        const tools = data.tools_used || [];
        setMessages((prev) => [...prev, { role: "assistant", content, tools }]);
      } else {
        let detail = "I'm having trouble answering right now. Please try again.";
        try {
          const err = await res.json();
          if (err?.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
        } catch {
          /* ignore */
        }
        setMessages((prev) => [...prev, { role: "assistant", content: detail }]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I can't reach the AI service right now. Please try again shortly." },
      ]);
    }
    setSending(false);
    requestAnimationFrame(scrollToEnd);
  };

  if (!user) {
    return (
      <div style={{ background: "#0a0f24", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>SB ME AI</h1>
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to access SB ME Intelligent AI.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#0a0f24", height: "calc(100vh - 64px)", display: "flex", flexDirection: "column", color: "#f0f6fc" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>SB ME AI</h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
          Sports intelligence & product assistant for Sportbook Me DFS AI
        </p>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "75%", padding: "12px 16px", borderRadius: 14,
              background: m.role === "user" ? "#c9a84c" : "#0a0f24",
              color: m.role === "user" ? "#0a0f24" : "#f0f6fc",
              border: m.role === "user" ? "none" : "1px solid #1e293b",
              fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap",
            }}>
              {m.content}
              {m.tools && m.tools.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 11, color: "#64748b" }}>
                  Used live data: {m.tools.join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEnd} />
      </div>

      <div style={{ padding: "12px 24px", borderTop: "1px solid #1e293b" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about Optimal%, SB OWN%, slates, Parlay Builder..."
            style={{
              flex: 1, padding: "12px 16px", borderRadius: 12, border: "1px solid #1e293b",
              background: "#0a0f24", color: "#f0f6fc", fontSize: 14, outline: "none",
            }} />
          <button onClick={send} disabled={sending} style={{
            padding: "12px 16px", borderRadius: 12, background: "#c9a84c", color: "#0a0f24",
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
