"use client";

import { useState, Suspense } from "react";
import { Search, Download, TrendingUp, TrendingDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchProjections, type PlayerProjection } from "@/lib/api";

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

// Demo projections per sport so the page is never empty
const DEMO_PROJECTIONS: Record<string, PlayerProjection[]> = {
  nfl: [
    { id:1, name:"Patrick Mahomes",  team:"KC",  slate_id:1, player_id:1,  salary:8400, roster_position:"QB",   projected_fp:38.2, ceiling:52.1, floor:24.4, ownership:28.4, leverage:1.1, value:4.55 },
    { id:2, name:"Josh Allen",       team:"BUF", slate_id:1, player_id:2,  salary:8200, roster_position:"QB",   projected_fp:35.8, ceiling:50.4, floor:22.1, ownership:22.1, leverage:2.3, value:4.37 },
    { id:3, name:"Tyreek Hill",      team:"MIA", slate_id:1, player_id:3,  salary:7800, roster_position:"WR",   projected_fp:29.4, ceiling:44.2, floor:14.5, ownership:18.6, leverage:1.9, value:3.77 },
    { id:4, name:"Davante Adams",    team:"NYJ", slate_id:1, player_id:4,  salary:7200, roster_position:"WR",   projected_fp:27.1, ceiling:38.8, floor:13.2, ownership:15.4, leverage:1.5, value:3.76 },
    { id:5, name:"Christian McCaffrey",team:"SF",slate_id:1,player_id:5,  salary:9000, roster_position:"RB",   projected_fp:33.6, ceiling:48.2, floor:19.8, ownership:32.5, leverage:-0.9,value:3.73 },
    { id:6, name:"Stefon Diggs",     team:"HOU", slate_id:1, player_id:6,  salary:6800, roster_position:"WR",   projected_fp:24.8, ceiling:36.1, floor:12.0, ownership:14.2, leverage:2.1, value:3.65 },
    { id:7, name:"Travis Kelce",     team:"KC",  slate_id:1, player_id:7,  salary:7600, roster_position:"TE",   projected_fp:26.4, ceiling:40.0, floor:14.1, ownership:24.8, leverage:0.2, value:3.47 },
    { id:8, name:"Dalton Kincaid",   team:"BUF", slate_id:1, player_id:8,  salary:5200, roster_position:"TE",   projected_fp:18.2, ceiling:28.4, floor:8.4,  ownership:9.1,  leverage:3.2, value:3.50 },
    { id:9, name:"DAL DST",          team:"DAL", slate_id:1, player_id:9,  salary:3200, roster_position:"DST",  projected_fp:10.4, ceiling:22.5, floor:2.0,  ownership:6.4,  leverage:1.8, value:3.25 },
    { id:10,name:"Breece Hall",      team:"NYJ", slate_id:1, player_id:10, salary:6600, roster_position:"RB",   projected_fp:24.2, ceiling:36.6, floor:11.8, ownership:16.3, leverage:0.9, value:3.67 },
  ],
  nba: [
    { id:1, name:"Nikola Jokić",     team:"DEN", slate_id:1, player_id:1,  salary:11200, roster_position:"C",  projected_fp:62.4, ceiling:82.1, floor:42.2, ownership:28.2, leverage:0.8, value:5.57 },
    { id:2, name:"Luka Dončić",      team:"DAL", slate_id:1, player_id:2,  salary:10800, roster_position:"PG", projected_fp:58.8, ceiling:78.4, floor:38.4, ownership:24.5, leverage:1.2, value:5.44 },
    { id:3, name:"Shai Gilgeous-Alexander",team:"OKC",slate_id:1,player_id:3,salary:10400,roster_position:"SG",projected_fp:54.2,ceiling:72.1,floor:36.2,ownership:22.1,leverage:1.8,value:5.21},
    { id:4, name:"Giannis Antetokounmpo",team:"MIL",slate_id:1,player_id:4,salary:10800,roster_position:"PF",projected_fp:58.1,ceiling:76.4,floor:38.8,ownership:26.4,leverage:0.4,value:5.38},
    { id:5, name:"LeBron James",     team:"LAL", slate_id:1, player_id:5,  salary:9800,  roster_position:"SF", projected_fp:48.6, ceiling:66.2, floor:30.4, ownership:20.4, leverage:1.4, value:4.96 },
    { id:6, name:"Anthony Davis",    team:"LAL", slate_id:1, player_id:6,  salary:10200, roster_position:"PF", projected_fp:52.4, ceiling:70.8, floor:34.2, ownership:24.1, leverage:0.9, value:5.14 },
    { id:7, name:"Trae Young",       team:"ATL", slate_id:1, player_id:7,  salary:8400,  roster_position:"PG", projected_fp:44.8, ceiling:62.4, floor:26.2, ownership:16.4, leverage:2.8, value:5.33 },
    { id:8, name:"Jayson Tatum",     team:"BOS", slate_id:1, player_id:8,  salary:9600,  roster_position:"SF", projected_fp:50.2, ceiling:68.4, floor:32.4, ownership:22.8, leverage:1.1, value:5.23 },
  ],
  mlb: [
    { id:1, name:"Shohei Ohtani",    team:"LAD", slate_id:1, player_id:1,  salary:5800, roster_position:"OF",  projected_fp:18.4, ceiling:32.2, floor:8.4,  ownership:32.4, leverage:-1.2,value:3.17 },
    { id:2, name:"Mookie Betts",     team:"LAD", slate_id:1, player_id:2,  salary:5200, roster_position:"OF",  projected_fp:15.8, ceiling:28.4, floor:6.2,  ownership:18.4, leverage:1.4, value:3.04 },
    { id:3, name:"Freddie Freeman",  team:"LAD", slate_id:1, player_id:3,  salary:4800, roster_position:"1B",  projected_fp:14.2, ceiling:25.6, floor:5.8,  ownership:14.2, leverage:2.1, value:2.96 },
    { id:4, name:"Gerrit Cole",      team:"NYY", slate_id:1, player_id:4,  salary:10200,roster_position:"P",   projected_fp:28.8, ceiling:44.2, floor:14.4, ownership:24.1, leverage:0.6, value:2.82 },
    { id:5, name:"Paul Goldschmidt", team:"STL", slate_id:1, player_id:5,  salary:4400, roster_position:"1B",  projected_fp:12.4, ceiling:22.4, floor:4.8,  ownership:10.4, leverage:2.8, value:2.82 },
    { id:6, name:"Bryce Harper",     team:"PHI", slate_id:1, player_id:6,  salary:5000, roster_position:"1B",  projected_fp:14.8, ceiling:26.4, floor:6.4,  ownership:16.2, leverage:1.6, value:2.96 },
  ],
  nhl: [
    { id:1, name:"Connor McDavid",   team:"EDM", slate_id:1, player_id:1,  salary:9000, roster_position:"C",   projected_fp:22.4, ceiling:36.2, floor:10.4, ownership:38.2, leverage:-2.1,value:2.49 },
    { id:2, name:"Nathan MacKinnon", team:"COL", slate_id:1, player_id:2,  salary:8600, roster_position:"C",   projected_fp:20.8, ceiling:34.4, floor:9.8,  ownership:28.4, leverage:0.4, value:2.42 },
    { id:3, name:"Auston Matthews",  team:"TOR", slate_id:1, player_id:3,  salary:8400, roster_position:"C",   projected_fp:20.2, ceiling:33.2, floor:9.2,  ownership:26.2, leverage:1.2, value:2.40 },
    { id:4, name:"David Pastrnak",   team:"BOS", slate_id:1, player_id:4,  salary:8000, roster_position:"W",   projected_fp:18.8, ceiling:30.4, floor:8.4,  ownership:22.4, leverage:1.8, value:2.35 },
    { id:5, name:"Andrei Vasilevskiy",team:"TBL",slate_id:1, player_id:5,  salary:7800, roster_position:"G",   projected_fp:24.2, ceiling:40.8, floor:8.2,  ownership:18.4, leverage:2.4, value:3.10 },
  ],
  ufc: [
    { id:1, name:"Jon Jones",        team:"HW",  slate_id:1, player_id:1,  salary:10800,roster_position:"CPT",  projected_fp:48.0, ceiling:80.0, floor:12.0, ownership:28.4, leverage:1.2, value:4.44 },
    { id:2, name:"Islam Makhachev",  team:"LW",  slate_id:1, player_id:2,  salary:9800, roster_position:"F",    projected_fp:38.4, ceiling:72.0, floor:10.4, ownership:22.4, leverage:2.1, value:3.92 },
    { id:3, name:"Sean O'Malley",    team:"BW",  slate_id:1, player_id:3,  salary:8800, roster_position:"F",    projected_fp:32.2, ceiling:68.0, floor:8.0,  ownership:18.4, leverage:3.2, value:3.66 },
  ],
  pga: [
    { id:1, name:"Scottie Scheffler",team:"PGA", slate_id:1, player_id:1,  salary:11800,roster_position:"G",   projected_fp:38.4, ceiling:52.2, floor:24.4, ownership:28.4, leverage:0.2, value:3.25 },
    { id:2, name:"Rory McIlroy",     team:"PGA", slate_id:1, player_id:2,  salary:10800,roster_position:"G",   projected_fp:34.8, ceiling:48.4, floor:20.2, ownership:22.4, leverage:1.4, value:3.22 },
    { id:3, name:"Jon Rahm",         team:"PGA", slate_id:1, player_id:3,  salary:10400,roster_position:"G",   projected_fp:33.2, ceiling:46.8, floor:18.8, ownership:18.4, leverage:2.2, value:3.19 },
  ],
  soccer: [
    { id:1, name:"Erling Haaland",   team:"MCI", slate_id:1, player_id:1,  salary:12000,roster_position:"FWD", projected_fp:28.4, ceiling:44.2, floor:12.4, ownership:34.2, leverage:-0.8,value:2.37 },
    { id:2, name:"Kylian Mbappé",    team:"RMA", slate_id:1, player_id:2,  salary:11200,roster_position:"FWD", projected_fp:26.8, ceiling:42.4, floor:10.8, ownership:28.4, leverage:0.8, value:2.39 },
    { id:3, name:"Kevin De Bruyne",  team:"MCI", slate_id:1, player_id:3,  salary:10400,roster_position:"MID", projected_fp:24.2, ceiling:38.4, floor:10.4, ownership:22.4, leverage:1.8, value:2.33 },
  ],
  mls: [
    { id:1, name:"Lionel Messi",     team:"MIA", slate_id:1, player_id:1,  salary:11200,roster_position:"FWD", projected_fp:26.4, ceiling:42.2, floor:10.4, ownership:38.4, leverage:-2.4,value:2.36 },
    { id:2, name:"Lorenzo Insigne",  team:"TOR", slate_id:1, player_id:2,  salary:8400, roster_position:"MID", projected_fp:18.4, ceiling:30.4, floor:8.4,  ownership:16.4, leverage:2.8, value:2.19 },
    { id:3, name:"Carlos Vela",      team:"LAFC",slate_id:1, player_id:3,  salary:8000, roster_position:"F/M", projected_fp:17.2, ceiling:28.4, floor:7.4,  ownership:14.2, leverage:3.1, value:2.15 },
  ],
  ncaaf: [
    { id:1, name:"Caleb Williams",   team:"USC", slate_id:1, player_id:1,  salary:8800, roster_position:"QB",  projected_fp:38.4, ceiling:56.2, floor:22.4, ownership:32.4, leverage:0.4, value:4.36 },
    { id:2, name:"Marvin Harrison Jr.",team:"OSU",slate_id:1,player_id:2,  salary:7400, roster_position:"WR",  projected_fp:28.4, ceiling:44.2, floor:14.4, ownership:22.4, leverage:2.1, value:3.84 },
  ],
  ncaam: [
    { id:1, name:"Zach Edey",        team:"PUR", slate_id:1, player_id:1,  salary:10800,roster_position:"C",   projected_fp:52.4, ceiling:72.2, floor:32.4, ownership:42.4, leverage:-1.8,value:4.85 },
    { id:2, name:"Hunter Dickinson",  team:"KAN", slate_id:1, player_id:2,  salary:9800, roster_position:"C",   projected_fp:46.8, ceiling:66.4, floor:28.4, ownership:32.4, leverage:0.8, value:4.78 },
  ],
  ncaaw: [
    { id:1, name:"Caitlin Clark",    team:"IOWA",slate_id:1, player_id:1,  salary:11200,roster_position:"PG",  projected_fp:56.4, ceiling:80.2, floor:34.4, ownership:52.4, leverage:-4.2,value:5.04 },
    { id:2, name:"Angel Reese",      team:"LSU", slate_id:1, player_id:2,  salary:9800, roster_position:"PF",  projected_fp:44.8, ceiling:64.2, floor:26.4, ownership:34.4, leverage:1.8, value:4.57 },
  ],
  boxing: [
    { id:1, name:"Canelo Álvarez",   team:"SMW", slate_id:1, player_id:1,  salary:10800,roster_position:"CPT", projected_fp:44.0, ceiling:76.0, floor:10.0, ownership:28.4, leverage:1.2, value:4.07 },
    { id:2, name:"Tyson Fury",       team:"HW",  slate_id:1, player_id:2,  salary:10400,roster_position:"F",   projected_fp:38.4, ceiling:70.0, floor:8.0,  ownership:22.4, leverage:2.4, value:3.69 },
  ],
};

function ProjectionsInner() {
  const [activeSport, setActiveSport] = useState("nba");
  const [activePosition, setActivePosition] = useState("All");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"projected_fp" | "value" | "ownership" | "salary">("projected_fp");

  const sport = SPORTS.find(s => s.id === activeSport) || SPORTS[1];

  const { data: liveData, isLoading } = useQuery({
    queryKey: ["projections", activeSport],
    queryFn: () => fetchProjections(1),
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
          style={{ background: "#161b22", border: "1px solid #30363d", color: "#00dc82" }}>
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
              {isLowOwn && <span className="text-[8px] px-1.5 py-0.5 rounded font-black uppercase" style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82" }}>LOW OWN</span>}
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
            color: isHighValue ? "#00dc82" : "#8b949e",
          }}>
          {p.value?.toFixed(2)}x
        </span>
      </td>
      <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{p.ownership.toFixed(1)}%</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {p.leverage > 0
            ? <TrendingUp className="size-3" style={{ color: "#00dc82" }} />
            : <TrendingDown className="size-3" style={{ color: "#f85149" }} />}
          <span className="text-xs font-bold" style={{ color: p.leverage > 0 ? "#00dc82" : "#f85149" }}>
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
