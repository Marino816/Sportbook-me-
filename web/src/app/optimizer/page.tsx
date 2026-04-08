"use client";

import { Settings2, Play, Lock, Ban, ListFilter, Calculator, Loader2, Download } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { runOptimizer, fetchSubscriptionStatus, type LineupResponse, type SubscriptionStatus } from "@/lib/api";
import { useState, useEffect } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const SPORTS = [
  { id: "NFL",    label: "NFL",    emoji: "🏈", color: "#d4ac0d",
    positions: ["QB","RB","WR","TE","K","DST","FLEX"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "NBA",    label: "NBA",    emoji: "🏀", color: "#f97316",
    positions: ["PG","SG","SF","PF","C","G","F","UTIL"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "MLB",    label: "MLB",    emoji: "⚾", color: "#3b82f6",
    positions: ["P","C","1B","2B","3B","SS","OF","UTIL"],
    salaryMin: 34000, salaryMax: 35000 },
  { id: "NHL",    label: "NHL",    emoji: "🏒", color: "#06b6d4",
    positions: ["C","W","D","G","UTIL"],
    salaryMin: 44000, salaryMax: 45000 },
  { id: "SOCCER", label: "SOCCER", emoji: "⚽", color: "#22c55e",
    positions: ["GK","DEF","MID","FWD"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "MLS",    label: "MLS",    emoji: "🥅", color: "#0ea5e9",
    positions: ["GK","DEF","MID","FWD","F/M"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "UFC",    label: "UFC",    emoji: "🥊", color: "#ef4444",
    positions: ["F","CPT"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "PGA",    label: "PGA",    emoji: "⛳", color: "#10b981",
    positions: ["G","CPT"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "NCAAF",  label: "NCAAF",  emoji: "🏟️", color: "#a855f7",
    positions: ["QB","RB","WR","TE","K","DST","FLEX"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "NCAAM",  label: "NCAAM",  emoji: "🏀", color: "#6366f1",
    positions: ["PG","SG","SF","PF","C","G","F","UTIL"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "NCAAW",  label: "NCAAW",  emoji: "🏀", color: "#ec4899",
    positions: ["PG","SG","SF","PF","C","G","F","UTIL"],
    salaryMin: 49000, salaryMax: 50000 },
  { id: "BOXING", label: "BOXING", emoji: "🥋", color: "#f59e0b",
    positions: ["F","CPT"],
    salaryMin: 49000, salaryMax: 50000 },
];

export default function OptimizerPage() {
  const [sport, setSport] = useState("NBA");
  const [site, setSite] = useState("DraftKings");
  const [lineupCount, setLineupCount] = useState(1);
  const [maxPerTeam, setMaxPerTeam] = useState(4);
  const [maxExposure, setMaxExposure] = useState(100);
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);

  useEffect(() => {
    async function load() {
      try { const res = await fetchSubscriptionStatus(); setSub(res.data); }
      catch (e) { console.error("Failed to load sub", e); }
    }
    load();
  }, []);

  const activeSport = SPORTS.find(s => s.id === sport) || SPORTS[1];
  const maxAllowed = sub?.plan === "Elite Stack" ? 150 : sub?.plan === "Pro Arena" ? 20 : 1;

  const optimizeMutation = useMutation({
    mutationFn: () => runOptimizer(1, {
      sport,
      site,
      num_lineups: Math.min(lineupCount, maxAllowed),
      min_salary: activeSport.salaryMin,
      max_salary: activeSport.salaryMax,
      max_players_per_team: maxPerTeam,
      max_exposure: maxExposure / 100,
    }),
  });

  const handleExport = () => {
    if (!optimizeMutation.data?.data) return;
    const lines = optimizeMutation.data.data.map((l: LineupResponse, i: number) =>
      `Lineup ${i + 1},Salary: $${l.total_salary.toLocaleString()},Proj: ${l.projected_score.toFixed(2)}\n` +
      l.players.map(p => `${p.roster_position},Player #${p.player_id},$${p.salary.toLocaleString()},${p.projected_fp.toFixed(1)}`).join("\n")
    ).join("\n\n");
    const blob = new Blob([lines], { type: "text/csv" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a");
    a.href = url; a.download = `${sport}_lineups.csv`; a.click();
  };

  return (
    <div className="flex-1 overflow-hidden h-full flex flex-col lg:flex-row" style={{ background: "#0d1117" }}>

      {/* ── SIDEBAR ── */}
      <div className="w-full lg:w-88 flex-shrink-0 flex flex-col overflow-y-auto scroll-hide"
        style={{ background: "#0d1117", borderRight: "1px solid #30363d", width: "340px" }}>

        {/* Header */}
        <div className="px-5 py-4 border-b" style={{ borderColor: "#30363d" }}>
          <h1 className="text-xl font-black tracking-tight text-white">Lineup Optimizer</h1>
          <p className="text-xs mt-0.5" style={{ color: "#8b949e" }}>
            SCIP integer programming engine — {activeSport.emoji} {activeSport.label}
          </p>
        </div>

        <div className="p-4 space-y-5 flex-1">

          {/* ── 12-SPORT SELECTOR ── */}
          <section>
            <p className="text-[9px] font-black uppercase tracking-widest mb-3" style={{ color: "#8b949e" }}>
              <Settings2 className="size-3 inline mr-1" />Select Sport
            </p>
            <div className="grid grid-cols-3 gap-1.5">
              {SPORTS.map((s) => {
                const isActive = sport === s.id;
                return (
                  <button key={s.id}
                    onClick={() => setSport(s.id)}
                    className="flex flex-col items-center gap-1 py-2 px-1 rounded-xl transition-all duration-150 text-center"
                    style={{
                      background: isActive ? `${s.color}22` : "#161b22",
                      border: isActive ? `1px solid ${s.color}55` : "1px solid #30363d",
                    }}>
                    <span className="text-lg leading-none">{s.emoji}</span>
                    <span className="text-[8px] font-black uppercase leading-none"
                      style={{ color: isActive ? s.color : "#8b949e" }}>{s.label}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* ── POSITIONS (for reference) ── */}
          <section>
            <p className="text-[9px] font-black uppercase tracking-widest mb-2" style={{ color: "#8b949e" }}>
              {activeSport.label} Roster Positions
            </p>
            <div className="flex flex-wrap gap-1.5">
              {activeSport.positions.map(pos => (
                <span key={pos} className="px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-wider"
                  style={{ background: `${activeSport.color}22`, color: activeSport.color, border: `1px solid ${activeSport.color}33` }}>
                  {pos}
                </span>
              ))}
            </div>
          </section>

          {/* ── SITE TOGGLE ── */}
          <section>
            <p className="text-[9px] font-black uppercase tracking-widest mb-2" style={{ color: "#8b949e" }}>Target Site</p>
            <div className="grid grid-cols-2 gap-2">
              {["DraftKings", "FanDuel"].map(s => (
                <button key={s} onClick={() => setSite(s)}
                  className="py-2.5 rounded-xl text-sm font-black transition-all"
                  style={{
                    background: site === s ? "#00dc82" : "#161b22",
                    color: site === s ? "#0d1117" : "#8b949e",
                    border: site === s ? "none" : "1px solid #30363d",
                    boxShadow: site === s ? "0 2px 12px rgba(0,220,130,0.3)" : "none",
                  }}>
                  {s}
                </button>
              ))}
            </div>
          </section>

          {/* ── LINEUP COUNT ── */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[9px] font-black uppercase tracking-widest" style={{ color: "#8b949e" }}>Number of Lineups</p>
              <span className="text-sm font-black"
                style={{ color: lineupCount > maxAllowed ? "#f85149" : "#00dc82" }}>
                {lineupCount}/{maxAllowed}
              </span>
            </div>
            <input type="range" min="1" max="150"
              value={lineupCount}
              onChange={e => setLineupCount(parseInt(e.target.value))}
              className="w-full accent-green-400" />
            {lineupCount > maxAllowed && (
              <div className="mt-2 p-3 rounded-xl text-xs" style={{ background: "rgba(248,81,73,0.1)", border: "1px solid rgba(248,81,73,0.3)" }}>
                <p className="font-black text-red-400 mb-1">Plan limit: {maxAllowed} lineups</p>
                <Link href="/billing" className="text-white font-black underline text-[10px]">
                  Upgrade for more →
                </Link>
              </div>
            )}
          </section>

          {/* ── ADVANCED RULES ── */}
          <section>
            <p className="text-[9px] font-black uppercase tracking-widest mb-3" style={{ color: "#8b949e" }}>
              <ListFilter className="size-3 inline mr-1" />Advanced Rules
            </p>
            <div className="space-y-3">
              {[
                { label: "Max Players per Team", value: maxPerTeam, min: 1, max: 8, onChange: setMaxPerTeam },
                { label: "Global Max Exposure %", value: maxExposure, min: 5, max: 100, onChange: setMaxExposure },
              ].map(({ label, value, min, max, onChange }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: "#c9d1d9" }}>{label}</span>
                  <input type="number" value={value} min={min} max={max}
                    onChange={e => onChange(parseInt(e.target.value) || min)}
                    className="w-16 rounded-lg px-2 py-1 text-right text-sm font-bold outline-none"
                    style={{ background: "#161b22", border: "1px solid #30363d", color: "#00dc82" }} />
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* ── GENERATE BUTTON ── */}
        <div className="p-4 border-t" style={{ borderColor: "#30363d" }}>
          <button onClick={() => optimizeMutation.mutate()}
            disabled={optimizeMutation.isPending}
            className="w-full py-3.5 rounded-xl font-black text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all hover:opacity-90 disabled:opacity-60"
            style={{
              background: "#00dc82", color: "#0d1117",
              boxShadow: "0 4px 20px rgba(0,220,130,0.4)",
            }}>
            {optimizeMutation.isPending
              ? <><Loader2 className="size-5 animate-spin" /> Solving Constraints...</>
              : <><Play className="size-4 fill-current" /> Generate {Math.min(lineupCount, maxAllowed)} Lineup{lineupCount > 1 ? "s" : ""}</>}
          </button>
        </div>
      </div>

      {/* ── MAIN WORKSPACE ── */}
      <div className="flex-1 flex flex-col overflow-y-auto" style={{ background: "#0d1117" }}>

        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b" style={{ borderColor: "#30363d" }}>
          <div className="flex gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold"
              style={{ background: "#161b22", border: "1px solid #30363d" }}>
              <Lock className="size-3 text-emerald-400" /> 0 Locked
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold"
              style={{ background: "#161b22", border: "1px solid #30363d" }}>
              <Ban className="size-3 text-red-400" /> 0 Excluded
            </div>
            {optimizeMutation.data?.data && (
              <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-black"
                style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82" }}>
                ✓ {optimizeMutation.data.data.length} lineup{optimizeMutation.data.data.length > 1 ? "s" : ""} generated
              </div>
            )}
          </div>
          {optimizeMutation.data?.data && (
            <button onClick={handleExport}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition-all hover:opacity-80"
              style={{ background: "#161b22", border: "1px solid #30363d", color: "#00dc82" }}>
              <Download className="size-3.5" /> Export CSV
            </button>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          {optimizeMutation.isPending ? (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <div className="w-12 h-12 rounded-full border-4 border-t-transparent animate-spin"
                style={{ borderColor: activeSport.color, borderTopColor: "transparent" }} />
              <p className="text-sm font-bold" style={{ color: "#8b949e" }}>
                Running SCIP optimizer for {activeSport.emoji} {activeSport.label}...
              </p>
            </div>
          ) : optimizeMutation.isError ? (
            <div className="rounded-2xl p-8 flex flex-col items-center justify-center text-center"
              style={{ background: "rgba(248,81,73,0.08)", border: "1px solid rgba(248,81,73,0.3)" }}>
              <p className="text-lg font-black text-red-400 mb-2">Generation Failed</p>
              <p className="text-sm max-w-md" style={{ color: "#8b949e" }}>
                {optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "An error occurred while building lineups."}
              </p>
              <button onClick={() => optimizeMutation.reset()}
                className="mt-4 px-4 py-2 rounded-xl text-xs font-black"
                style={{ background: "rgba(248,81,73,0.15)", color: "#f85149", border: "1px solid rgba(248,81,73,0.3)" }}>
                Try Again
              </button>
            </div>
          ) : optimizeMutation.data?.data ? (
            <div className="space-y-4">
              {optimizeMutation.data.data.map((l: LineupResponse, i: number) => (
                <LineupCard key={i} lineup={l} index={i} sportColor={activeSport.color} sportLabel={activeSport.label} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full min-h-64 text-center">
              <div className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl mb-4"
                style={{ background: "#161b22", border: "1px solid #30363d" }}>
                {activeSport.emoji}
              </div>
              <h3 className="text-lg font-black mb-2 text-white">Ready to Optimize</h3>
              <p className="text-sm max-w-sm" style={{ color: "#8b949e" }}>
                Select your sport & settings, then click <strong style={{ color: "#00dc82" }}>Generate Lineups</strong> to run the SCIP solver. Results appear here.
              </p>
              <div className="mt-6 flex gap-3 flex-wrap justify-center">
                {activeSport.positions.map(pos => (
                  <span key={pos} className="px-3 py-1.5 rounded-xl text-xs font-black uppercase tracking-wider"
                    style={{ background: `${activeSport.color}15`, color: activeSport.color, border: `1px solid ${activeSport.color}30` }}>
                    {pos}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LineupCard({ lineup, index, sportColor, sportLabel }: { lineup: LineupResponse; index: number; sportColor: string; sportLabel: string }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "#161b22", border: "1px solid #30363d" }}>
      <div className="h-0.5 w-full" style={{ background: sportColor }} />
      <div className="px-5 py-3 flex items-center justify-between cursor-pointer"
        style={{ borderBottom: expanded ? "1px solid #30363d" : "none" }}
        onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <span className="text-sm font-black text-white">Lineup {index + 1}</span>
          <span className="text-[10px] px-2 py-0.5 rounded font-black uppercase"
            style={{ background: `${sportColor}22`, color: sportColor }}>
            {sportLabel}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div style={{ color: "#8b949e" }}>
            Salary: <span className="font-black text-white">${lineup.total_salary.toLocaleString()}</span>
          </div>
          <div style={{ color: "#8b949e" }}>
            Proj: <span className="font-black" style={{ color: sportColor }}>{lineup.projected_score.toFixed(2)}</span>
          </div>
          <span className="text-xs" style={{ color: "#8b949e" }}>{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && (
        <table className="w-full text-sm">
          <tbody>
            {lineup.players.map((p, j) => (
              <tr key={j} style={{ borderBottom: "1px solid #21262d" }}
                onMouseEnter={e => (e.currentTarget.style.background = "#1c2128")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                <td className="px-4 py-2.5 w-16">
                  <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded"
                    style={{ background: `${sportColor}22`, color: sportColor }}>
                    {p.roster_position}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-bold text-white">Player #{p.player_id}</td>
                <td className="px-4 py-2.5 text-right" style={{ color: "#8b949e" }}>${p.salary.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-right font-black" style={{ color: sportColor }}>{p.projected_fp.toFixed(1)} FP</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
