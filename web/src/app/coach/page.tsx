"use client";

import { useEffect, useState } from "react";
import { getCoachPerformance, getCoachRecommendations } from "@/lib/api-phase7";

export default function CoachPage() {
  const [perf, setPerf] = useState<any>(null);
  const [recs, setRecs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getCoachPerformance(), getCoachRecommendations()])
      .then(([p, r]) => { setPerf(p.data); setRecs(r.data?.recommendations || []); })
      .catch(e => { if (e.message?.includes("403")) setError("Coach requires Pro Arena."); else setError(e.message); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="min-h-screen bg-background p-8"><p>Loading...</p></main>;

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Coach</h1>
    {error && <p className="text-red-400 mb-4">{error}</p>}
    {perf && (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="rounded-xl border p-3"><p className="text-xs text-muted">ROI</p><p className="font-black text-lg">{perf.roi?.roi ?? "N/A"}%</p></div>
        <div className="rounded-xl border p-3"><p className="text-xs text-muted">Cash Rate</p><p className="font-black text-lg">{perf.cash_rate ?? "N/A"}%</p></div>
        <div className="rounded-xl border p-3"><p className="text-xs text-muted">Net Profit</p><p className="font-black text-lg">${perf.roi?.net_profit ?? "N/A"}</p></div>
        <div className="rounded-xl border p-3"><p className="text-xs text-muted">Entries</p><p className="font-black text-lg">{perf.roi?.total_entries ?? "N/A"}</p></div>
      </div>
    )}
    <h2 className="font-bold mb-2">Recommendations</h2>
    <div className="space-y-3">
      {recs.map((r, i) => <div key={i} className="rounded-xl border p-3"><p className="font-semibold text-sm">{r.rec || r.recommendation}</p><p className="text-xs text-muted">{r.rationale}</p></div>)}
    </div>
  </main>;
}