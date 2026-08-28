"use client";

import { useAuth } from "@/lib/auth";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Send, Loader2 } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";
import { AppShell } from "@/components/app-shell";
import { VoiceMicButton } from "@/components/voice-mic-button";
import { useVoiceInput } from "@/hooks/use-voice-input";
import {
  VOICE_DENIED_HINT,
  VOICE_LISTENING_HINT,
  VOICE_UNSUPPORTED_HINT,
} from "@/lib/voice-input";
import {
  EMPTY_AI_CONTEXT,
  formatContextStrip,
  type ConversationContext,
  type SuggestedAction,
} from "@/lib/ai-session";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);
const SESSION_KEY = "sbme_ai_session_v1";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  actions?: SuggestedAction[];
}

const WELCOME =
  "Welcome to SB ME AI. I can help with DFS slate metrics and SportsGameOdds market intelligence from SB ME's live cache: live/upcoming/final games, scores, current lines, Fair Odds, Book Consensus, player and team props, alternate lines, period markets, and soccer (EPL, Champions League, and the other supported leagues). If something is not in the cache, I will say it is unavailable — I will not invent odds or bookmaker availability.";

function loadSession(): { convId: string | null; context: ConversationContext; messages: ChatMessage[] } {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return { convId: null, context: { ...EMPTY_AI_CONTEXT }, messages: [{ role: "assistant", content: WELCOME }] };
    const parsed = JSON.parse(raw);
    return {
      convId: parsed.convId || null,
      context: { ...EMPTY_AI_CONTEXT, ...(parsed.context || {}) },
      messages: Array.isArray(parsed.messages) && parsed.messages.length
        ? parsed.messages
        : [{ role: "assistant", content: WELCOME }],
    };
  } catch {
    return { convId: null, context: { ...EMPTY_AI_CONTEXT }, messages: [{ role: "assistant", content: WELCOME }] };
  }
}

export default function AIPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: WELCOME },
  ]);
  const [input, setInput] = useState("");
  const inputRef = useRef(input);
  inputRef.current = input;
  const [sending, setSending] = useState(false);
  const [context, setContext] = useState<ConversationContext>({ ...EMPTY_AI_CONTEXT });
  const [convId, setConvId] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const contextRef = useRef(context);
  const convRef = useRef(convId);
  const messagesRef = useRef(messages);
  contextRef.current = context;
  convRef.current = convId;
  messagesRef.current = messages;

  const scrollToEnd = () => chatEnd.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => {
    const s = loadSession();
    setMessages(s.messages);
    setContext(s.context);
    setConvId(s.convId);
    setSessionReady(true);
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        convId,
        context,
        messages: messages.slice(-24),
      }));
    } catch {
      /* ignore */
    }
  }, [convId, context, messages, sessionReady]);

  useEffect(() => {
    try {
      const draft = sessionStorage.getItem("sbme_ai_draft");
      if (draft) {
        sessionStorage.removeItem("sbme_ai_draft");
        setInput(draft);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const voice = useVoiceInput({
    getBaseline: () => inputRef.current,
    onTranscript: (text) => setInput(text),
  });

  useEffect(() => {
    if (!voice.listening) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        voice.cancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [voice.listening, voice.cancel]);

  const send = async (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text || sending) return;
    if (voice.listening) voice.stop();
    setInput("");
    setSending(true);
    const prior = messagesRef.current;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const token = localStorage.getItem("sbme_dfs_token");
      const history = prior
        .filter((m) => m.content !== WELCOME)
        .slice(-20)
        .map((m) => ({ role: m.role, content: m.content }));
      const current = contextRef.current;
      const res = await fetch(`${API_BASE}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message: text,
          page: "ai",
          conversation_id: convRef.current || undefined,
          history,
          context: current,
          sport: current.sport || undefined,
          platform: current.platform || undefined,
          slate_id: current.slate_id || undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const content = data.content || data.response || data.data?.response || "I processed your request.";
        const tools = data.tools_used || [];
        const actions: SuggestedAction[] = data.suggested_actions || [];
        if (data.conversation_id) {
          setConvId(data.conversation_id);
          convRef.current = data.conversation_id;
        }
        if (data.context) {
          setContext(data.context);
          contextRef.current = data.context;
        }
        setMessages((prev) => [...prev, { role: "assistant", content, tools, actions }]);
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

  const onAction = (action: SuggestedAction) => {
    if (action.href) {
      router.push(action.href);
      return;
    }
    if (action.prompt) send(action.prompt);
  };

  const strip = formatContextStrip(context);

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
    <AppShell>
    <div style={{ height: "calc(100vh - 64px)", display: "flex", flexDirection: "column", color: "#f0f6fc" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>SB ME AI</h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
          Sports intelligence & product assistant for Sportbook Me DFS AI
        </p>
        {strip ? (
          <p style={{ color: "#c9a84c", fontSize: 12, margin: "8px 0 0", letterSpacing: "0.02em" }}>
            {strip}
          </p>
        ) : null}
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
                <div style={{ marginTop: 8, fontSize: 11, color: "#94a3b8" }}>
                  Used live data: {m.tools.join(", ")}
                </div>
              )}
              {m.role === "assistant" && m.actions && m.actions.length > 0 && (
                <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {m.actions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={() => onAction(action)}
                      style={{
                        padding: "6px 10px",
                        borderRadius: 999,
                        border: "1px solid rgba(201, 168, 76, 0.35)",
                        background: "rgba(201, 168, 76, 0.1)",
                        color: "#e4cc78",
                        fontSize: 11,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEnd} />
      </div>

      <div style={{ padding: "12px 24px", borderTop: "1px solid #1e293b" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask SB ME Intelligence..."
            style={{
              flex: 1, padding: "12px 16px", borderRadius: 12, border: "1px solid #1e293b",
              background: "#0a0f24", color: "#f0f6fc", fontSize: 14, outline: "none",
            }} />
          <VoiceMicButton
            listening={voice.listening}
            status={voice.status}
            supported={voice.supported !== false}
            disabled={sending}
            onToggle={voice.toggle}
            onCancel={voice.cancel}
          />
          <button onClick={() => send()} disabled={sending} style={{
            padding: "12px 16px", borderRadius: 12, background: "#c9a84c", color: "#0a0f24",
            border: "none", cursor: "pointer", fontWeight: 700, display: "flex", alignItems: "center", gap: 6,
            minHeight: 44,
          }}>
            {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            Send
          </button>
        </div>
        <div className="sbme-voice-status" aria-live="polite">
          {voice.listening ? (
            <>
              <strong>{VOICE_LISTENING_HINT}</strong>
              <button type="button" className="sbme-voice-cancel" onClick={voice.cancel}>
                Cancel
              </button>
            </>
          ) : voice.status === "denied" ? (
            <span>{VOICE_DENIED_HINT}</span>
          ) : voice.supported === false || voice.status === "unsupported" ? (
            <span>{VOICE_UNSUPPORTED_HINT}</span>
          ) : voice.status === "error" ? (
            <span>Voice input could not start. You can still type.</span>
          ) : null}
        </div>
      </div>
    </div>
    </AppShell>
  );
}
