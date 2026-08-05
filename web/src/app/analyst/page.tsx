"use client";

import { useState } from "react";
import { getPlayerAnalysis, getTopEdges } from "@/lib/api-phase7";
import Phase7Error, { isErrorStatus } from "@/components/Phase7Error";

type State = { kind: "loading" | "ready" | "error"; errorKind?: string; message?: string };

export default function AnalystPage() {
  const [playerData, setPlayerData] = useState<any>(null);
  const [edges, setEdges] = useState<any[]>([]);
  const [playerId, setPlayerId] = useState("");
  const [state, setState] = useState<State>({ kind: "loading" });

  const analyze = () => {
    const id = parseInt(playerId);
    if (!id || id <= 0) return;
    setState({ kind: "loading" });
    Promise.all([getPlayerAnalysis(id), getTopEdges(1)])
      .then(([p, e]) => { setPlayerData(p.data); setEdges(e.data.edges || []); setState({ kind: "ready" }); })
      .catch((e) => setState({ kind: "error", errorKind: isErrorStatus(e?.status || 500), message: e.message }));
  };

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Analyst</h1>
    <p className="text-muted text-sm mb-4">Structured sports analysis and SB-Me Edge scores.</p>

    <div className="flex flex-wrap gap-2 mb-6">
      <input value={playerId} onChange={e => setPlayerId(e.target.value)} className="rounded-xl border px-3 py-1 bg-transparent w-24 text-sm" placeholder="Player ID" />
      <button onClick={analyze} disabled={!playerId || state.kind === "loading"} className="rounded-xl border px-4 py-1 text-sm font-semibold">Analyze</button>
    </div>

    {state.kind === "error" && <Phase7Error kind={state.errorKind as any || "server-error"} message={state.message} onRetry={playerId ? analyze : undefined} />}

    {state.kind === "ready" && playerData && (
      <div className="rounded-2xl border p-4 mb-6">
        <h2 className="font-bold">{playerData.headline}</h2>
        <p className="text-sm text-muted mt-1">{playerData.summary}</p>
        <p className="text-sm mt-2">Confidence: {(playerData.confidence_score || 0).toFixed(2)}{playerData.edge_score != null ? ` | Edge: ${playerData.edge_score}` : ""}</p>
        {playerData.stale_data_flag && <p className="text-yellow-400 text-xs mt-1">Stale data</p>}
        {playerData.missing_data_flags?.length > 0 && <p className="text-yellow-400 text-xs mt-1">Missing: {playerData.missing_data_flags.join(", ")}</p>}
      </div>
    )}

    {state.kind === "ready" && !playerData && <Phase7Error kind="no-data" message="Enter a player ID and click Analyze." />}

    {edges.length > 0 && (
      <>
        <h2 className="font-bold mb-2">Top SB-Me Edge</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {edges.map((e, i) => <div key={i} className="rounded-xl border p-3"><p className="font-semibold text-sm">{e.name}</p><p className="text-lg font-black">{e.edge_score || e.score}</p></div>)}
        </div>
      </>
    )}
  </main>;
}