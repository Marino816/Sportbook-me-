"use client";

import { useEffect, useState } from "react";
import { getPlayerAnalysis, getTopEdges } from "@/lib/api-phase7";

export default function AnalystPage() {
  const [playerData, setPlayerData] = useState<any>(null);
  const [edges, setEdges] = useState<any[]>([]);
  const [playerId, setPlayerId] = useState("1");
  const [loading, setLoading] = useState(false);

  const analyze = () => {
    setLoading(true);
    Promise.all([getPlayerAnalysis(parseInt(playerId)), getTopEdges(1)])
      .then(([p, e]) => { setPlayerData(p.data); setEdges(e.data.edges || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { analyze(); }, []);

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Analyst</h1>
    <div className="flex gap-2 my-4">
      <input value={playerId} onChange={e => setPlayerId(e.target.value)} className="rounded-xl border px-3 py-1 bg-transparent w-20 text-sm" />
      <button onClick={analyze} disabled={loading} className="rounded-xl border px-4 py-1 text-sm">Analyze</button>
    </div>
    {playerData && <div className="rounded-2xl border p-4 mb-6"><h2 className="font-bold">{playerData.headline}</h2><p className="text-sm text-muted">{playerData.summary}</p><p className="text-sm mt-2">Confidence: {(playerData.confidence_score || 0).toFixed(2)}</p></div>}
    <h2 className="font-bold mb-2">Top SB-Me Edge</h2>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {edges.map((e, i) => <div key={i} className="rounded-xl border p-3"><p className="font-semibold text-sm">{e.name}</p><p className="text-lg font-black">{e.edge_score || e.score}</p></div>)}
    </div>
  </main>;
}