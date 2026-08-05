"use client";

import { useState, useRef, useEffect } from "react";
import { sendAssistantChat, getStrategyModes, setStrategyMode } from "@/lib/api-phase7";
import Phase7Error, { isErrorStatus } from "@/components/Phase7Error";

interface Message { role: string; content: string; intent?: string; confidence?: number; modules?: string[]; evidence?: string; freshness?: string; missing?: string[]; version?: string; }

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [convId, setConvId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [modes, setModes] = useState<any[]>([]);
  const [mode, setMode] = useState("balanced");
  const [modesLoadError, setModesLoadError] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getStrategyModes()
      .then(r => setModes(r.data.modes || []))
      .catch(() => setModesLoadError(true));
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages(m => [...m, { role: "user", content: text }]);
    setLoading(true);
    setChatError(null);
    sendAssistantChat(text, convId || undefined)
      .then(r => {
        setConvId(r.data.conversation_id);
        const resp = r.data.response;
        setMessages(m => [...m, {
          role: "assistant",
          content: resp.recommendation || resp.summary || "",
          intent: resp.intent,
          confidence: resp.confidence,
          modules: resp.modules_consulted,
          evidence: resp.evidence?.summary,
          freshness: resp.data_freshness,
          missing: resp.missing_data,
          version: resp.model_version,
        }]);
      })
      .catch(e => setChatError(e.message))
      .finally(() => setLoading(false));
  };

  const changeMode = (m: string) => {
    setMode(m);
    setStrategyMode(m).catch(() => {});
  };

  return <main className="min-h-screen bg-background p-4 md:p-8 flex flex-col max-w-2xl mx-auto">
    <h1 className="text-2xl font-black italic">SB-Me AI Assistant</h1>
    <p className="text-muted text-sm mb-4">Sports intelligence orchestration.</p>

    {modesLoadError && <Phase7Error kind="provider-unavailable" message="Strategy modes unavailable." />}

    {modes.length > 0 && (
      <div className="flex gap-2 mb-4 flex-wrap">
        {modes.map((m: any) => (
          <button key={m.mode} onClick={() => changeMode(m.mode)}
            className={`text-xs px-3 py-1 rounded-xl border ${mode === m.mode ? "bg-green-500/10 border-green-500/30 text-green-400" : "border-border"}`}>
            {m.mode?.replace(/_/g, " ") || m.name}
          </button>
        ))}
      </div>
    )}

    <div className="flex-1 space-y-3 mb-4 max-h-[60vh] overflow-y-auto">
      {messages.map((m, i) => (
        <div key={i} className={`p-3 rounded-2xl max-w-[90%] ${m.role === "user" ? "bg-green-500/10 ml-auto" : "bg-card border"}`}>
          <p className="text-sm">{m.content}</p>
          <div className="text-[10px] text-muted mt-1 flex flex-wrap gap-x-2">
            {m.intent && <span>Intent: {m.intent}</span>}
            {m.confidence != null && <span>| Conf: {m.confidence.toFixed ? m.confidence.toFixed(2) : m.confidence}</span>}
            {m.modules && <span>| Modules: {m.modules.join(", ")}</span>}
            {m.freshness && <span>| Freshness: {m.freshness}</span>}
            {m.version && <span>| v{m.version}</span>}
          </div>
          {m.missing && m.missing.length > 0 && <p className="text-[10px] text-yellow-400 mt-1">Missing: {m.missing.join(", ")}</p>}
        </div>
      ))}
      {loading && <p className="text-muted text-sm italic">Thinking...</p>}
      {chatError && <Phase7Error kind="server-error" message={chatError} />}
      <div ref={bottomRef} />
    </div>

    <div className="flex gap-2">
      <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} className="flex-1 rounded-xl border px-3 py-2 bg-transparent text-sm" placeholder="Ask about lineups, matchups, performance..." />
      <button onClick={send} disabled={loading} className="rounded-xl border px-4 py-2 text-sm font-semibold bg-green-500/10 text-green-400">Send</button>
    </div>
  </main>;
}