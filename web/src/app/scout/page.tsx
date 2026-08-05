"use client";

import { useEffect, useState } from "react";
import { getScoutEvents, getScoutProviders, getScoutFreshness } from "@/lib/api-phase7";

export default function ScoutPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [freshness, setFreshness] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getScoutEvents(), getScoutProviders(), getScoutFreshness()])
      .then(([ev, pr, fr]) => { setEvents(ev.data.events || []); setProviders(pr.data.providers || []); setFreshness(fr.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="min-h-screen bg-background p-8"><p>Loading...</p></main>;

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Scout</h1>
    <p className="text-muted mb-6">Real-time sports intelligence events.</p>
    {freshness && <div className="mb-6 p-4 rounded-2xl border"><h2 className="font-bold text-sm">Freshness: {freshness.overall_freshness || freshness.overall || "unknown"}</h2></div>}
    <h2 className="font-bold mb-2">Events ({events.length})</h2>
    <div className="grid grid-cols-1 gap-3">
      {events.map((e, i) => (
        <div key={i} className={`rounded-xl border p-4 ${e.severity === "critical" ? "border-red-500/30 bg-red-500/5" : ""}`}>
          <span className="text-xs px-2 py-0.5 rounded font-bold uppercase">{e.severity}</span>
          <p className="text-sm mt-1">{e.event_type}</p>
          <p className="text-xs text-muted">{e.timestamp}</p>
        </div>
      ))}
    </div>
    <h2 className="font-bold mt-8 mb-2">Providers ({providers.length})</h2>
    <div className="flex flex-wrap gap-2">
      {providers.map((p, i) => <span key={i} className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-400">{p.name || p.provider}</span>)}
    </div>
  </main>;
}