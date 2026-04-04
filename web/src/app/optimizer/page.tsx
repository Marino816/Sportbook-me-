"use client";

import { Settings2, Play, Lock, Ban, ListFilter, Calculator, Loader2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { runOptimizer, fetchSubscriptionStatus, type LineupResponse, type SubscriptionStatus } from "@/lib/api";
import { useState, useEffect } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function OptimizerPage() {
  const [lineupCount, setLineupCount] = useState(1);
  const [site, setSite] = useState("DraftKings");
  const [sport, setSport] = useState("NBA");
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchSubscriptionStatus();
        setSub(res.data);
      } catch (e) {
        console.error("Failed to load sub in optimizer", e);
      }
    }
    load();
  }, []);

  const maxAllowed = sub?.plan === "Elite Stack" ? 150 : sub?.plan === "Pro Arena" ? 20 : 1;

  const optimizeMutation = useMutation({
    mutationFn: () => runOptimizer(1, { 
      sport, 
      site, 
      num_lineups: lineupCount, 
      min_salary: 49000, 
      max_salary: 50000 
    })
  });

  const handleGenerate = () => {
    optimizeMutation.mutate();
  };

  return (
    <div className="flex-1 overflow-hidden h-full bg-background flex flex-col lg:flex-row">
      {/* Sidebar Controls */}
      <div className="w-full lg:w-96 glass border-r border-border flex flex-col h-full overflow-y-auto z-10">
        <div className="p-6 border-b border-border">
          <h1 className="text-2xl font-bold text-foreground">Optimizer</h1>
          <p className="text-sm text-muted-foreground mt-1">Configure your generation rules.</p>
        </div>
        
        <div className="p-6 space-y-8 flex-1">
          {/* Contest Settings */}
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
              <Settings2 className="size-4" /> Builder Settings
            </h2>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1.5 block">Target Site</label>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => setSite("DraftKings")} className={`py-2 rounded-lg text-sm font-medium border ${site === "DraftKings" ? "bg-primary text-primary-foreground border-transparent" : "bg-secondary text-muted-foreground border-border"}`}>DraftKings</button>
                  <button onClick={() => setSite("FanDuel")} className={`py-2 rounded-lg text-sm font-medium border ${site === "FanDuel" ? "bg-primary text-primary-foreground border-transparent" : "bg-secondary text-muted-foreground border-border"}`}>FanDuel</button>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium mb-1.5 block">Sport</label>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => setSport("NBA")} className={`py-2 rounded-lg text-sm font-medium border ${sport === "NBA" ? "bg-secondary/50 text-foreground border-primary/50 ring-1 ring-primary" : "bg-secondary text-muted-foreground border-border"}`}>NBA</button>
                  <button onClick={() => setSport("MLB")} className={`py-2 rounded-lg text-sm font-medium border ${sport === "MLB" ? "bg-secondary/50 text-foreground border-primary/50 ring-1 ring-primary" : "bg-secondary text-muted-foreground border-border"}`}>MLB</button>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium mb-1.5 flex justify-between">
                  <span>Number of Lineups</span>
                  <span className={cn("font-bold", lineupCount > maxAllowed ? "text-red-500" : "text-primary")}>
                    {lineupCount} / {maxAllowed}
                  </span>
                </label>
                <input 
                  type="range" 
                  min="1" 
                  max={sub?.plan === "Elite Stack" ? 150 : 150} // Let them slide to see what they are missing
                  value={lineupCount} 
                  onChange={(e) => setLineupCount(parseInt(e.target.value))} 
                  className="w-full accent-primary" 
                />
                {lineupCount > maxAllowed && (
                  <div className="mt-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <p className="text-[10px] text-red-500 font-bold uppercase italic leading-tight">
                      Limit Exceeded. Current plan allows max {maxAllowed} lineups.
                    </p>
                    <Link href="/billing" className="text-[10px] text-white font-black underline uppercase mt-2 block">
                       Upgrade to {sub?.plan === "Starter" ? "Pro" : "Elite"} for more →
                    </Link>
                  </div>
                )}
                {sub?.plan !== "Elite Stack" && lineupCount <= maxAllowed && (
                   <p className="text-[10px] text-muted-foreground mt-2 italic">
                     Generating {lineupCount} lineups. {sub?.plan === "Starter" ? "Pro allows 20." : "Elite allows 150."}
                   </p>
                )}
              </div>
            </div>
          </section>

          {/* Advanced Rules */}
          <section>
             <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
              <ListFilter className="size-4" /> Advanced Rules
            </h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Max Players per Team</span>
                <input type="number" defaultValue="4" className="w-16 bg-secondary border border-border rounded px-2 py-1 text-right text-sm" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Min Salary Threshold</span>
                <input type="number" defaultValue="49000" className="w-20 bg-secondary border border-border rounded px-2 py-1 text-right text-sm" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Global Max Exposure</span>
                <input type="number" defaultValue="100" className="w-16 bg-secondary border border-border rounded px-2 py-1 text-right text-sm" />
              </div>
            </div>
          </section>
        </div>

        <div className="p-4 border-t border-border bg-card/50">
          <button onClick={handleGenerate} disabled={optimizeMutation.isPending} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3 rounded-xl flex items-center justify-center gap-2 shadow-xl shadow-primary/20 transition-all disabled:opacity-70">
            {optimizeMutation.isPending ? <Loader2 className="size-5 animate-spin" /> : <Play className="size-5 fill-current" />}
            {optimizeMutation.isPending ? "Solving Constraints..." : `Generate ${lineupCount} Lineups`}
          </button>
        </div>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 p-8 bg-black/20 flex flex-col overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
           <div className="flex gap-4">
             <div className="glass px-4 py-2 rounded-lg border border-border flex items-center gap-2">
               <Lock className="size-4 text-green-500" />
               <span className="text-sm font-medium">0 Locked</span>
             </div>
             <div className="glass px-4 py-2 rounded-lg border border-border flex items-center gap-2">
               <Ban className="size-4 text-red-500" />
               <span className="text-sm font-medium">0 Excluded</span>
             </div>
           </div>
        </div>

        {/* Results / Empty State */}
        {optimizeMutation.data?.data ? (
          <div className="space-y-6">
            {optimizeMutation.data.data.map((l: LineupResponse, i: number) => (
              <div key={i} className="glass rounded-xl border border-border overflow-hidden">
                <div className="bg-secondary/50 px-6 py-4 border-b border-border flex items-center justify-between">
                  <h3 className="font-bold">Lineup {i + 1}</h3>
                  <div className="flex gap-6 text-sm">
                    <div>Salary: <span className="font-bold text-foreground">${l.total_salary.toLocaleString()}</span></div>
                    <div>Proj FP: <span className="font-bold text-primary">{l.projected_score.toFixed(2)}</span></div>
                  </div>
                </div>
                <div className="p-0">
                  <table className="w-full text-sm">
                    <tbody>
                      {l.players.map((p, j) => (
                        <tr key={j} className="border-b border-border/50 last:border-0 hover:bg-secondary/20 transition-colors">
                          <td className="px-6 py-3 font-bold text-muted-foreground w-16">{p.roster_position}</td>
                          <td className="px-6 py-3 text-foreground font-medium">Player #{p.player_id}</td>
                          <td className="px-6 py-3 text-right">${p.salary.toLocaleString()}</td>
                          <td className="px-6 py-3 text-right text-primary font-bold">{p.projected_fp.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        ) : optimizeMutation.isError ? (
           <div className="flex-1 glass rounded-2xl border border-red-500/50 bg-red-500/5 flex flex-col items-center justify-center text-center p-12">
            <h3 className="text-xl font-bold text-red-500 mb-2">Generation Failed</h3>
            <p className="text-muted-foreground max-w-md">
              {optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "An unknown error occurred while building lineups."}
            </p>
          </div>
        ) : (
          <div className="flex-1 glass rounded-2xl border border-border border-dashed flex flex-col items-center justify-center text-center p-12">
            <div className="size-20 rounded-full bg-secondary flex items-center justify-center mb-6">
              <Calculator className="size-10 text-muted-foreground/50" />
            </div>
            <h3 className="text-xl font-bold mb-2">Ready to Optimize</h3>
            <p className="text-muted-foreground max-w-md">
              Configure your settings on the left and click generate to run the SCIP integer linear programming engine. Resulting lineups will appear here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
