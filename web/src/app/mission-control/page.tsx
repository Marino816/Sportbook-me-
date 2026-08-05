"use client";

import { useEffect, useState, useCallback } from "react";
import { getMissionControl, getDailyBriefing } from "@/lib/api-phase7";

interface Widget {
  widget_id: string;
  widget_type: string;
  title: string;
  stale_data_flag: boolean;
  missing_data_flags: string[];
  subscription_required: string;
}

export default function MissionControlPage() {
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [tier, setTier] = useState("free");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const mc = await getMissionControl();
      setWidgets(Object.values(mc.data.widgets) as Widget[]);
      setTier(mc.data.tier);
    } catch (e: any) {
      setError(e.message || "Failed");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <main className="min-h-screen bg-background p-8"><p>Loading...</p></main>;
  if (error) return <main className="min-h-screen bg-background p-8"><p className="text-red-400">{error}</p></main>;

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Mission Control</h1>
    <p className="text-muted mb-6">Tier: {tier} | Widgets: {widgets.length}</p>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {widgets.map((w, i) => (
        <div key={i} className="rounded-2xl border p-4">
          <h2 className="font-bold text-sm">{w.title}</h2>
          <span className="text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded">{w.subscription_required}</span>
          {w.stale_data_flag && <p className="text-yellow-400 text-xs mt-1">Stale</p>}
        </div>
      ))}
    </div>
  </main>;
}
