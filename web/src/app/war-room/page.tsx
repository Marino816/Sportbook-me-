"use client";

import { useEffect, useState } from "react";
import { getWarRoom } from "@/lib/api-phase7";

export default function WarRoomPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getWarRoom().then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <main className="min-h-screen bg-background p-8"><p>Loading...</p></main>;

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me War Room</h1>
    <p className="text-muted mb-6">Unified intelligence workspace.</p>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="rounded-2xl border p-4"><h2 className="font-bold text-sm">Active Alerts</h2><pre className="text-xs text-muted mt-2">{JSON.stringify(data?.active_alerts, null, 1)}</pre></div>
      <div className="rounded-2xl border p-4"><h2 className="font-bold text-sm">Top Edge</h2><pre className="text-xs text-muted mt-2">{JSON.stringify(data?.analyst_top_edge, null, 1)}</pre></div>
      <div className="rounded-2xl border p-4"><h2 className="font-bold text-sm">Builder</h2><p className="text-sm mt-2">Lineups ready: {data?.builder_lineups_ready}</p></div>
      <div className="rounded-2xl border p-4"><h2 className="font-bold text-sm">Coach</h2><p className="text-sm mt-2">ROI: {data?.coach_latest?.roi}%</p></div>
    </div>
  </main>;
}