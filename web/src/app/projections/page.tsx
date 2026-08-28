"use client";

import { useState, Suspense } from "react";
import { Search, Download, TrendingUp, TrendingDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchProjections, fetchDFSSlates, type PlayerProjection } from "@/lib/api";

const SPORTS = [
  { id: "nfl",    label: "NFL",    emoji: "🏈", color: "#d4ac0d",
    positions: ["All", "QB", "RB", "WR", "TE", "K", "DST", "FLEX"] },
  { id: "nba",    label: "NBA",    emoji: "🏀", color: "#f97316",
    positions: ["All", "PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"] },
  { id: "mlb",    label: "MLB",    emoji: "⚾", color: "#3b82f6",
    positions: ["All", "P", "C", "1B", "2B", "3B", "SS", "OF", "UTIL"] },
  { id: "nhl",    label: "NHL",    emoji: "🏒", color: "#06b6d4",
    positions: ["All", "C", "W", "D", "G", "UTIL"] },
  { id: "soccer", label: "SOCCER", emoji: "⚽", color: "#22c55e",
    positions: ["All", "GK", "DEF", "MID", "FWD"] },
  { id: "mls",    label: "MLS",    emoji: "🥅", color: "#0ea5e9",
    positions: ["All", "GK", "DEF", "MID", "FWD", "F/M"] },
  { id: "ufc",    label: "UFC",    emoji: "🥊", color: "#ef4444",
    positions: ["All", "F", "CPT"] },
  { id: "pga",    label: "PGA",    emoji: "⛳", color: "#10b981",
    positions: ["All", "G", "CPT"] },
  { id: "ncaaf",  label: "NCAAF",  emoji: "🏟️", color: "#a855f7",
    positions: ["All", "QB", "RB", "WR", "TE", "K", "DST", "FLEX"] },
  { id: "ncaam",  label: "NCAAM",  emoji: "🏀", color: "#6366f1",
    positions: ["All", "PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"] },
  { id: "ncaaw",  label: "NCAAW",  emoji: "🏀", color: "#ec4899",
    positions: ["All", "PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"] },
  { id: "boxing", label: "BOXING", emoji: "🥋", color: "#f59e0b",
    positions: ["All", "F", "CPT"] },
];

// No demo projections — real API data only.
// If live data is unavailable, show "Data currently unavailable".
const DEMO_PROJECTIONS: Record<string, PlayerProjection[]> = {};

function ProjectionsInner() {
  const [activeSport, setActiveSport] = useState("nba");
  const [activePosition, setActivePosition] = useState("All");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"projected_fp" | "value" | "ownership" | "salary">("projected_fp");

  const sport = SPORTS.find(s => s.id === activeSport) || SPORTS[1];

  const { data: slatesRes } = useQuery({
    queryKey: ["dfs-slates", activeSport],
    queryFn: () => fetchDFSSlates(undefined, activeSport.toUpperCase()),
    retry: 1,
  });
  const publishedSlateId = (slatesRes?.data ?? []).find((s) => s.status === "PUBLISHED")?.id;

  const { data: liveData, isLoading } = useQuery({
    queryKey: ["projections", publishedSlateId],
    queryFn: () => fetchProjections(publishedSlateId as number),
    enabled: publishedSlateId != null,
    retry: 1,
  });

  // Use live data if available, otherwise fall back to demo
  const rawPlayers: PlayerProjection[] =
    (liveData?.data && liveData.data.length > 0)
      ? liveData.data
      : (DEMO_PROJECTIONS[activeSport] || []);

  const players = rawPlayers
    .filter(p => activePosition === "All" || p.roster_position === activePosition)
    .filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || p.team?.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));

  const isDemo = !liveData?.data || liveData.data.length === 0;

  const handleExport = () => {
    const csv = ["Name,Team,Position,Salary,Proj FP,Ceiling,Floor,Value,Own%,Leverage",
      ...players.map(p => `${p.name},${p.team},${p.roster_position},${p.salary},${p.projected_fp.toFixed(1)},${p.ceiling.toFixed(1)},${p.floor.toFixed(1)},${p.value?.toFixed(2)},${p.ownership.toFixed(1)},${p.leverage.toFixed(1)}`)
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${activeSport}_projections.csv`; a.click();
  };

  return (
    <div className="flex-1 overflow-y-auto h-full" style={{ background: "#0d1117" }}>

      {/* ── TOP BAR ── */}
      <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "#30363d" }}>
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Projections</h1>
          <p className="text-sm mt-0.5" style={{ color: "#8b949e" }}>
            ML-powered projections — updated every 5 min
            {isDemo && !isLoading && <span className="ml-2 text-amber-400 font-bold">• Demo Mode</span>}
          </p>
        </div>
        <button onClick={handleExport}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all hover:opacity-90"
          style={{ background: "#161b22", border: "1px solid #30363d", color: "#c9a84c" }}>
          <Download className="size-4" /> Export CSV
        </button>
      </div>

      {/* ── 12-SPORT RAIL ── */}
      <div className="px-4 pt-4">
        <div className="flex gap-2 overflow-x-auto scroll-hide pb-2">
          {SPORTS.map((s) => {
            const isActive = activeSport === s.id;
            return (
              <button key={s.id}
                onClick={() => { setActiveSport(s.id); setActivePosition("All"); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-black uppercase tracking-wider whitespace-nowrap flex-shrink-0 transition-all duration-150"
                style={{
                  background: isActive ? s.color : "#161b22",
                  color: isActive ? "#0d1117" : "#8b949e",
                  border: isActive ? `1px solid ${s.color}` : "1px solid #30363d",
                  boxShadow: isActive ? `0 0 12px ${s.color}44` : "none",
                }}>
                <span>{s.emoji}</span><span>{s.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── POSITION FILTER + SEARCH ── */}
      <div className="px-4 pt-3 flex flex-wrap items-center gap-3">
        <div className="flex gap-1.5 flex-wrap">
          {sport.positions.map(pos => (
            <button key={pos}
              onClick={() => setActivePosition(pos)}
              className="px-3 py-1 rounded-lg text-xs font-black uppercase tracking-wider transition-all"
              style={{
                background: activePosition === pos ? `${sport.color}22` : "#161b22",
                color: activePosition === pos ? sport.color : "#8b949e",
                border: activePosition === pos ? `1px solid ${sport.color}55` : "1px solid #30363d",
              }}>
              {pos}
            </button>
          ))}
        </div>

        <div className="relative ml-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4" style={{ color: "#8b949e" }} />
          <input
            type="text"
            placeholder="Search players..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 rounded-xl text-sm w-56 outline-none"
            style={{ background: "#161b22", border: "1px solid #30363d", color: "#f0f6fc" }}
          />
        </div>
      </div>

      {/* ── TABLE ── */}
      <div className="px-4 pt-3 pb-8">
        <div className="rounded-2xl overflow-hidden" style={{ background: "#161b22", border: "1px solid #30363d" }}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "#0d1117", borderBottom: "1px solid #30363d" }}>
                  {[
                    { key: null, label: "Athlete" },
                    { key: null, label: "Pos" },
                    { key: "salary", label: "Salary" },
                    { key: "projected_fp", label: "Proj FP" },
                    { key: null, label: "Ceil" },
                    { key: null, label: "Floor" },
                    { key: "value", label: "Value" },
                    { key: "ownership", label: "Own %" },
                    { key: null, label: "Leverage" },
                  ].map(col => (
                    <th key={col.label}
                      className="px-4 py-3 text-left text-[10px] font-black uppercase tracking-wider cursor-pointer select-none"
                      style={{ color: sortBy === col.key ? sport.color : "#8b949e" }}
                      onClick={() => col.key && setSortBy(col.key as typeof sortBy)}>
                      {col.label}{col.key && sortBy === col.key ? " ↓" : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-sm" style={{ color: "#8b949e" }}>
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: sport.color, borderTopColor: "transparent" }} />
                        Loading live projections...
                      </div>
                    </td>
                  </tr>
                ) : players.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-sm" style={{ color: "#8b949e" }}>
                      No players match your filter.
                    </td>
                  </tr>
                ) : players.map((p, i) => (
                  <PlayerRow key={p.id} player={p} sportColor={sport.color} index={i} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlayerRow({ player: p, sportColor, index }: { player: PlayerProjection; sportColor: string; index: number }) {
  const isHighValue = p.value > 4.0;
  const isLowOwn = p.ownership < 15;
  return (
    <tr className="transition-colors" style={{ borderBottom: "1px solid #21262d" }}
      onMouseEnter={e => (e.currentTarget.style.background = "#1c2128")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-black"
            style={{ background: `${sportColor}22`, color: sportColor }}>
            {index + 1}
          </div>
          <div>
            <div className="font-bold text-white text-sm flex items-center gap-1.5">
              {p.name}
              {isLowOwn && <span className="text-[8px] px-1.5 py-0.5 rounded font-black uppercase" style={{ background: "rgba(0,220,130,0.15)", color: "#c9a84c" }}>LOW OWN</span>}
            </div>
            <div className="text-[10px] font-black uppercase mt-0.5" style={{ color: "#8b949e" }}>{p.team}</div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider"
          style={{ background: `${sportColor}22`, color: sportColor }}>
          {p.roster_position}
        </span>
      </td>
      <td className="px-4 py-3 font-bold text-sm" style={{ color: "#f0f6fc" }}>${p.salary.toLocaleString()}</td>
      <td className="px-4 py-3">
        <span className="text-base font-black" style={{ color: sportColor }}>{p.projected_fp.toFixed(1)}</span>
      </td>
      <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{p.ceiling.toFixed(1)}</td>
      <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{p.floor.toFixed(1)}</td>
      <td className="px-4 py-3">
        <span className="px-2 py-0.5 rounded text-xs font-black"
          style={{
            background: isHighValue ? "rgba(0,220,130,0.15)" : "#21262d",
            color: isHighValue ? "#c9a84c" : "#8b949e",
          }}>
          {p.value?.toFixed(2)}x
        </span>
      </td>
      <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{p.ownership.toFixed(1)}%</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {p.leverage > 0
            ? <TrendingUp className="size-3" style={{ color: "#c9a84c" }} />
            : <TrendingDown className="size-3" style={{ color: "#f85149" }} />}
          <span className="text-xs font-bold" style={{ color: p.leverage > 0 ? "#c9a84c" : "#f85149" }}>
            {p.leverage > 0 ? "+" : ""}{p.leverage.toFixed(1)}
          </span>
        </div>
      </td>
    </tr>
  );
}

export default function ProjectionsPage() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center" style={{ background: "#0d1117" }}>
        <div className="text-sm" style={{ color: "#8b949e" }}>Loading...</div>
      </div>
    }>
      <ProjectionsInner />
    </Suspense>
  );
}
