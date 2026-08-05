"use client";

import { useEffect, useState } from "react";
import { buildLineups, getBuilderStrategies, BuilderLineupRequest } from "@/lib/api-phase7";

export default function BuilderPage() {
  const [lineups, setLineups] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [platform, setPlatform] = useState("draftkings");
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getBuilderStrategies().then(r => setStrategies(r.data.strategies || [])).catch(() => {});
  }, []);

  const build = () => {
    setLoading(true); setError("");
    const req: BuilderLineupRequest = { slate_id: 1, platform, strategy, lineup_count: count };
    buildLineups(req).then(r => setLineups(r.data.lineups || [])).catch(e => setError(e.message)).finally(() => setLoading(false));
  };

  return <main className="min-h-screen bg-background p-4 md:p-8">
    <h1 className="text-2xl font-black italic">SB-Me Builder</h1>
    <div className="flex flex-wrap gap-2 my-4">
      <select value={platform} onChange={e => setPlatform(e.target.value)} className="rounded-xl border px-3 py-1 bg-transparent text-sm">
        <option value="draftkings">DraftKings</option>
        <option value="fanduel">FanDuel</option>
      </select>
      <select value={strategy} onChange={e => setStrategy(e.target.value)} className="rounded-xl border px-3 py-1 bg-transparent text-sm">
        <option value="balanced">Balanced</option>
        <option value="cash">Cash</option>
        <option value="aggressive">Aggressive</option>
      </select>
      <input type="number" min={1} max={150} value={count} onChange={e => setCount(parseInt(e.target.value) || 1)} className="rounded-xl border px-3 py-1 bg-transparent w-16 text-sm" />
      <button onClick={build} disabled={loading} className="rounded-xl border px-4 py-1 text-sm font-semibold bg-green-500/10 text-green-400">Build</button>
    </div>
    {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {lineups.map((lu, i) => (
        <div key={i} className="rounded-2xl border p-4">
          <h2 className="font-bold text-sm">Lineup #{lu.lineup_index}</h2>
          <p className="text-sm">Projected: {lu.projected_score} FP | Salary: ${lu.total_salary?.toLocaleString()}</p>
          <ul className="text-xs mt-2 space-y-1">{lu.players?.map((p: any, j: number) => <li key={j}>{p.name} - ${p.salary?.toLocaleString()} ({p.roster_position})</li>)}</ul>
        </div>
      ))}
    </div>
    {lineups.length === 0 && !loading && <p className="text-muted text-center py-12">Build a lineup to get started.</p>}
  </main>;
}