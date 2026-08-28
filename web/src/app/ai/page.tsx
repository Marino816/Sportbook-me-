"use client";

import { useAuth } from "@/lib/auth";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Send, Loader2, Zap } from "lucide-react";
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
  sessionContextView,
  type ConversationContext,
  type SuggestedAction,
} from "@/lib/ai-session";
import { ROOKIE_LEAGUES } from "@/lib/sgo-leagues";

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

const STARTERS = [
  { label: "Today's MLB games", prompt: "Today's MLB games" },
  { label: "Show today's player props", prompt: "Show today's player props" },
  { label: "Compare bookmaker prices", prompt: "Compare bookmaker prices" },
  { label: "Best available markets", prompt: "Best available markets" },
  { label: "Analyze my DFS slate", prompt: "Analyze my DFS slate" },
  { label: "Build a DraftKings lineup", prompt: "Build a DraftKings lineup" },
  { label: "EPL matches", prompt: "EPL matches" },
  { label: "Explain Fair Odds", prompt: "Explain Fair Odds" },
  { label: "Show Book Consensus", prompt: "Show Book Consensus" },
] as const;

const CAPABILITIES = [
  "LIVE GAMES",
  "MARKETS",
  "FAIR ODDS",
  "BOOK CONSENSUS",
  "PROPS",
  "DFS",
  `${ROOKIE_LEAGUES.length} LEAGUES`,
] as const;

function sanitizeMessages(list: ChatMessage[] | undefined): ChatMessage[] {
  return (list || []).filter((m) => m?.content && m.content !== WELCOME);
}

function loadSession(): { convId: string | null; context: ConversationContext; messages: ChatMessage[] } {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return { convId: null, context: { ...EMPTY_AI_CONTEXT }, messages: [] };
    const parsed = JSON.parse(raw);
    return {
      convId: parsed.convId || null,
      context: { ...EMPTY_AI_CONTEXT, ...(parsed.context || {}) },
      messages: sanitizeMessages(parsed.messages),
    };
  } catch {
    return { convId: null, context: { ...EMPTY_AI_CONTEXT }, messages: [] };
  }
}

export default function AIPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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

  const conversationActive = messages.some((m) => m.role === "user");
  const ctxView = sessionContextView(context);

  if (!user) {
    return (
      <div className="sbme-intel sbme-intel--gate">
        <h1>SB ME Intelligence™</h1>
        <p>Sign in to access SB ME Intelligence.</p>
      </div>
    );
  }

  return (
    <AppShell atmosphere="ai">
      <div className="sbme-intel">
        <header className="sbme-intel-head">
          <span className="sbme-intel-mark" aria-hidden><Zap size={18} /></span>
          <div className="sbme-intel-titles">
            <h1>SB ME Intelligence™</h1>
            <p>Sports Intelligence &amp; DFS AI</p>
          </div>
          <span className="sbme-intel-badge" title="Answers use SB ME cache and tools. Unavailable data is stated as unavailable.">
            SB ME CACHE
          </span>
        </header>

        <div className="sbme-intel-caps" aria-label="SB ME Intelligence capabilities">
          {CAPABILITIES.map((label) => (
            <span key={label} className="sbme-intel-cap">{label}</span>
          ))}
        </div>

        {ctxView ? (
          <div className="sbme-intel-ctx" aria-live="polite">
            {ctxView.line ? <span>{ctxView.line}</span> : null}
            {ctxView.locked ? <span className="sbme-intel-ctx-lock">{ctxView.locked}</span> : null}
          </div>
        ) : null}

        <div className="sbme-intel-body">
          {!conversationActive ? (
            <section className="sbme-intel-welcome">
              <h2>Command center</h2>
              <p>
                SB ME can assist with DFS, slate metrics, live/upcoming/final games,
                scores where available, current markets, Fair Odds, Book Consensus,
                player props, team props, alternate lines, period markets, and soccer
                supported leagues.
              </p>
              <ul>
                <li>DFS</li>
                <li>Slate metrics</li>
                <li>Live / upcoming / final games</li>
                <li>Scores where available</li>
                <li>Current markets</li>
                <li>Fair Odds</li>
                <li>Book Consensus</li>
                <li>Player props</li>
                <li>Team props</li>
                <li>Alternate lines</li>
                <li>Period markets</li>
                <li>Soccer supported leagues</li>
              </ul>
              <aside>
                If information is not available in SB ME&apos;s cache/data, SB ME will say it is unavailable.
                It will not invent odds, bookmaker availability, scores, injuries, projections, props, lines, or live events.
              </aside>
              <div className="sbme-intel-starters">
                {STARTERS.map((item) => (
                  <button
                    key={item.prompt}
                    type="button"
                    className="sbme-intel-starter"
                    onClick={() => send(item.prompt)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {messages.map((m, i) => (
            <div key={i} className={`sbme-intel-row sbme-intel-row--${m.role}`}>
              <div className={`sbme-intel-bubble sbme-intel-bubble--${m.role}`}>
                {m.role === "assistant" ? (
                  <span className="sbme-intel-bubble-mark" aria-hidden><Zap size={12} /></span>
                ) : null}
                <div className="sbme-intel-bubble-body">
                  {m.content}
                  {m.tools && m.tools.length > 0 && (
                    <div className="sbme-intel-tools">Used: {m.tools.join(", ")}</div>
                  )}
                  {m.role === "assistant" && m.actions && m.actions.length > 0 && (
                    <div className="sbme-intel-actions">
                      {m.actions.map((action) => (
                        <button
                          key={action.id}
                          type="button"
                          className="sbme-intel-action"
                          onClick={() => onAction(action)}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {sending ? <div className="sbme-intel-pending">Working…</div> : null}
          <div ref={chatEnd} />
        </div>

        <div className="sbme-intel-dock">
          <div className={`sbme-intel-composer${voice.listening ? " sbme-intel-composer--listening" : ""}`}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask SB ME Intelligence…"
              aria-label="Ask SB ME Intelligence"
            />
            <VoiceMicButton
              listening={voice.listening}
              status={voice.status}
              supported={voice.supported !== false}
              disabled={sending}
              onToggle={voice.toggle}
              onCancel={voice.cancel}
            />
            <button
              type="button"
              className="sbme-intel-send"
              onClick={() => send()}
              disabled={sending}
            >
              {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Send
            </button>
          </div>
          <div className="sbme-voice-status" aria-live="polite">
            {voice.listening ? (
              <>
                <span className="sbme-voice-wave" aria-hidden><i /><i /><i /></span>
                <strong>{VOICE_LISTENING_HINT}</strong>
                <button type="button" className="sbme-voice-cancel" onClick={voice.stop}>Stop</button>
                <button type="button" className="sbme-voice-cancel" onClick={voice.cancel}>Cancel</button>
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
