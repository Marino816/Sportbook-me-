"use client";

import { useState, useRef } from "react";
import { sendAssistantChat, getStrategyModes, setStrategyMode } from "@/lib/api-phase7";

interface Message { role: string; content: string; intent?: string; confidence?: number }

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [convId, setConvId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages(m => [...m, { role: "user", content: text }]);
    setLoading(true);
    sendAssistantChat(text, convId || undefined)
      .then(r => {
        setConvId(r.data.conversation_id);
        setMessages(m => [...m, { role: "assistant", content: r.data.response.recommendation, intent: r.data.response.intent, confidence: r.data.response.confidence }]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  return <main className="min-h-screen bg-background p-4 md:p-8 flex flex-col max-w-2xl mx-auto">
    <h1 className="text-2xl font-black italic">SB-Me AI Assistant</h1>
    <p className="text-muted text-sm mb-4">Sports intelligence orchestration.</p>
    <div className="flex-1 space-y-3 mb-4 max-h-[60vh] overflow-y-auto">
      {messages.map((m, i) => (
        <div key={i} className={`p-3 rounded-2xl max-w-[85%] ${m.role === "user" ? "bg-green-500/10 ml-auto" : "bg-card border"}`}>
          <p className="text-sm">{m.content}</p>
          {m.intent && <p className="text-xs text-muted mt-1">Intent: {m.intent} | Conf: {(m.confidence || 0).toFixed(2)}</p>}
        </div>
      ))}
      {loading && <p className="text-muted text-sm italic">Thinking...</p>}
      <div ref={bottomRef} />
    </div>
    <div className="flex gap-2">
      <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} className="flex-1 rounded-xl border px-3 py-2 bg-transparent text-sm" placeholder="Ask about lineups, matchups, performance..." />
      <button onClick={send} disabled={loading} className="rounded-xl border px-4 py-2 text-sm font-semibold bg-green-500/10 text-green-400">Send</button>
    </div>
  </main>;
}