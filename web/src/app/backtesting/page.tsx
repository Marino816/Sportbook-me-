"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPerformanceStats } from "@/lib/api";
import { TrendingUp, TrendingDown, Activity, Target, BarChart3, Calendar } from "lucide-react";

const SPORTS = [
  { id: "all",    label: "All Sports", emoji: "🎯", color: "#00dc82" },
  { id: "nfl",    label: "NFL",        emoji: "🏈", color: "#d4ac0d" },
  { id: "nba",    label: "NBA",        emoji: "🏀", color: "#f97316" },
  { id: "mlb",    label: "MLB",        emoji: "⚾", color: "#3b82f6" },
  { id: "nhl",    label: "NHL",        emoji: "🏒", color: "#06b6d4" },
  { id: "soccer", label: "SOCCER",     emoji: "⚽", color: "#22c55e" },
  { id: "mls",    label: "MLS",        emoji: "🥅", color: "#0ea5e9" },
  { id: "ufc",    label: "UFC",        emoji: "🥊", color: "#ef4444" },
  { id: "pga",    label: "PGA",        emoji: "⛳", color: "#10b981" },
  { id: "ncaaf",  label: "NCAAF",      emoji: "🏟️", color: "#a855f7" },
  { id: "ncaam",  label: "NCAAM",      emoji: "🏀", color: "#6366f1" },
  { id: "ncaaw",  label: "NCAAW",      emoji: "🏀", color: "#ec4899" },
  { id: "boxing", label: "BOXING",     emoji: "🥋", color: "#f59e0b" },
];

// Simulated historical slate performance per sport
const SPORT_STATS: Record<string, {
  roi: string; winRate: string; mae: string; totalSlates: number;
  recentSlates: { date: string; place: string; score: number; proj: number; cash: boolean }[];
}> = {
  all: {
    roi: "+18.4%", winRate: "58.2%", mae: "3.21", totalSlates: 284,
    recentSlates: [
      { date: "Apr 7", place: "1st / 4,820",  score: 218.4, proj: 204.8, cash: true  },
      { date: "Apr 6", place: "12th / 3,210", score: 196.2, proj: 198.4, cash: true  },
      { date: "Apr 5", place: "480th / 6,120",score: 172.4, proj: 188.2, cash: false },
      { date: "Apr 4", place: "4th / 2,840",  score: 224.8, proj: 210.4, cash: true  },
      { date: "Apr 3", place: "22nd / 5,210", score: 188.4, proj: 192.8, cash: true  },
    ],
  },
  nfl: {
    roi: "+22.8%", winRate: "61.4%", mae: "2.98", totalSlates: 48,
    recentSlates: [
      { date: "Week 18", place: "3rd / 8,420",  score: 198.4, proj: 182.8, cash: true  },
      { date: "Week 17", place: "28th / 6,210", score: 162.4, proj: 174.2, cash: false },
      { date: "Week 16", place: "1st / 5,840",  score: 224.8, proj: 208.4, cash: true  },
    ],
  },
  nba: {
    roi: "+16.2%", winRate: "56.8%", mae: "3.42", totalSlates: 112,
    recentSlates: [
      { date: "Apr 7", place: "1st / 4,820",  score: 288.4, proj: 274.8, cash: true  },
      { date: "Apr 6", place: "12th / 3,210", score: 256.2, proj: 268.4, cash: true  },
      { date: "Apr 5", place: "480th / 6,120",score: 222.4, proj: 248.2, cash: false },
    ],
  },
  mlb: {
    roi: "+21.4%", winRate: "59.6%", mae: "2.84", totalSlates: 96,
    recentSlates: [
      { date: "Apr 7", place: "8th / 12,840",  score: 148.4, proj: 138.8, cash: true  },
      { date: "Apr 6", place: "62nd / 9,210",  score: 124.2, proj: 132.4, cash: true  },
      { date: "Apr 5", place: "1840th / 18,120",score:102.4, proj: 118.2, cash: false },
    ],
  },
  nhl: {
    roi: "+14.8%", winRate: "54.2%", mae: "3.84", totalSlates: 72,
    recentSlates: [
      { date: "Apr 7", place: "4th / 2,420",   score: 58.4, proj: 52.8, cash: true  },
      { date: "Apr 6", place: "22nd / 1,810",  score: 44.2, proj: 48.4, cash: true  },
    ],
  },
  soccer: { roi: "+11.2%", winRate: "52.4%", mae: "4.12", totalSlates: 28, recentSlates: [
    { date: "Apr 6", place: "14th / 1,420", score: 84.4, proj: 78.8, cash: true  },
  ]},
  mls: { roi: "+9.8%", winRate: "51.2%", mae: "4.44", totalSlates: 18, recentSlates: [
    { date: "Apr 5", place: "28th / 840",   score: 72.4, proj: 68.8, cash: true  },
  ]},
  ufc: { roi: "+32.4%", winRate: "64.2%", mae: "6.12", totalSlates: 24, recentSlates: [
    { date: "Apr 6", place: "1st / 2,820",  score: 152.4, proj: 124.8, cash: true  },
    { date: "Mar 30", place: "18th / 1,840",score: 112.4, proj: 118.8, cash: false },
  ]},
  pga: { roi: "+28.6%", winRate: "62.4%", mae: "5.12", totalSlates: 32, recentSlates: [
    { date: "Apr 7", place: "2nd / 6,420", score: 348.4, proj: 318.8, cash: true  },
  ]},
  ncaaf: { roi: "+19.4%", winRate: "58.8%", mae: "3.24", totalSlates: 26, recentSlates: [
    { date: "Jan 8", place: "5th / 4,420", score: 188.4, proj: 172.8, cash: true  },
  ]},
  ncaam: { roi: "+24.2%", winRate: "61.8%", mae: "3.84", totalSlates: 14, recentSlates: [
    { date: "Apr 6", place: "3rd / 3,820", score: 248.4, proj: 228.8, cash: true  },
  ]},
  ncaaw: { roi: "+18.8%", winRate: "56.4%", mae: "3.62", totalSlates: 10, recentSlates: [
    { date: "Apr 5", place: "7th / 2,820", score: 228.4, proj: 214.8, cash: true  },
  ]},
  boxing: { roi: "+28.4%", winRate: "63.2%", mae: "6.84", totalSlates: 8, recentSlates: [
    { date: "Mar 30", place: "1st / 1,820", score: 168.4, proj: 142.8, cash: true  },
  ]},
};

// Simulated bar chart data (last 10 slates ROI distribution)
const BAR_DATA = [12.4, -4.2, 28.8, 8.4, -2.8, 44.2, 18.4, 6.2, 32.8, 22.4];

export default function BacktestingPage() {
  const [activeSport, setActiveSport] = useState("all");
  const [range, setRange] = useState<"7d" | "30d" | "90d" | "all">("30d");

  const { data: livePerf } = useQuery({
    queryKey: ["performance"],
    queryFn: fetchPerformanceStats,
    retry: 1,
  });

  const sport = SPORTS.find(s => s.id === activeSport) || SPORTS[0];
  const stats = SPORT_STATS[activeSport] || SPORT_STATS["all"];

  const roi  = livePerf?.data?.total_roi  || stats.roi;
  const winRate = livePerf?.data?.win_rate || stats.winRate;
  const mae  = livePerf?.data?.ave_error  || stats.mae;

  const roiNum = parseFloat(roi.replace(/[^0-9.-]/g, ""));
  const roiPositive = roiNum >= 0;

  return (
    <div className="flex-1 overflow-y-auto h-full" style={{ background: "#0d1117" }}>

      {/* ── TOP BAR ── */}
      <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "#30363d" }}>
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Backtesting</h1>
          <p className="text-sm mt-0.5" style={{ color: "#8b949e" }}>
            Historical model performance — AI accuracy analysis across all slates
          </p>
        </div>
        <div className="flex gap-2">
          {(["7d","30d","90d","all"] as const).map(r => (
            <button key={r} onClick={() => setRange(r)}
              className="px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all"
              style={{
                background: range === r ? sport.color : "#161b22",
                color: range === r ? "#0d1117" : "#8b949e",
                border: range === r ? "none" : "1px solid #30363d",
              }}>
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* ── SPORT FILTER ── */}
      <div className="px-4 pt-4">
        <div className="flex gap-2 overflow-x-auto scroll-hide pb-2">
          {SPORTS.map((s) => {
            const isActive = activeSport === s.id;
            return (
              <button key={s.id}
                onClick={() => setActiveSport(s.id)}
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

      <div className="p-4 space-y-4">

        {/* ── KPI CARDS ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: "ROI", value: roi, icon: roiPositive ? TrendingUp : TrendingDown, positive: roiPositive, sub: `${range} period` },
            { label: "Win Rate", value: winRate, icon: Target, positive: true, sub: "Cash rate" },
            { label: "Model MAE", value: mae, icon: Activity, positive: true, sub: "Lower is better" },
            { label: "Total Slates", value: stats.totalSlates.toString(), icon: Calendar, positive: true, sub: `${sport.label} slates` },
          ].map(({ label, value, icon: Icon, positive, sub }) => (
            <div key={label} className="rounded-2xl p-4"
              style={{ background: "#161b22", border: "1px solid #30363d" }}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-[9px] font-black uppercase tracking-widest" style={{ color: "#8b949e" }}>{label}</span>
                <div className="p-1.5 rounded-lg"
                  style={{ background: positive ? "rgba(0,220,130,0.15)" : "rgba(248,81,73,0.15)" }}>
                  <Icon className="size-3.5" style={{ color: positive ? "#00dc82" : "#f85149" }} />
                </div>
              </div>
              <div className="text-2xl font-black mb-0.5"
                style={{ color: label === "ROI" ? (roiPositive ? "#00dc82" : "#f85149") : "#f0f6fc" }}>
                {value}
              </div>
              <div className="text-[10px]" style={{ color: "#8b949e" }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* ── ROI BAR CHART ── */}
        <div className="rounded-2xl p-5" style={{ background: "#161b22", border: "1px solid #30363d" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="size-4" style={{ color: sport.color }} />
              <h2 className="font-black text-sm text-white">Slate-by-Slate ROI %</h2>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded"
              style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82" }}>
              Last 10 Slates
            </span>
          </div>
          <div className="flex items-end gap-2 h-32">
            {BAR_DATA.map((val, i) => {
              const positive = val >= 0;
              const height = Math.abs(val) / 50 * 100;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${val > 0 ? "+" : ""}${val}%`}>
                  <div className="w-full rounded-t-md transition-all hover:opacity-80 cursor-pointer"
                    style={{
                      height: `${Math.max(height, 8)}%`,
                      background: positive ? sport.color : "#f85149",
                      opacity: 0.85,
                      minHeight: 6,
                    }} />
                  <span className="text-[8px] font-bold" style={{ color: positive ? sport.color : "#f85149" }}>
                    {val > 0 ? "+" : ""}{val}%
                  </span>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-[9px]" style={{ color: "#8b949e" }}>10 slates ago</span>
            <span className="text-[9px]" style={{ color: "#8b949e" }}>Latest</span>
          </div>
        </div>

        {/* ── RECENT SLATES TABLE ── */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "#161b22", border: "1px solid #30363d" }}>
          <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "#30363d" }}>
            <h2 className="font-black text-sm text-white">Recent Slate Results</h2>
            <span className="text-[10px] font-black px-2 py-0.5 rounded"
              style={{ background: `${sport.color}22`, color: sport.color }}>
              {sport.emoji} {sport.label}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "#0d1117", borderBottom: "1px solid #30363d" }}>
                {["Date", "Finish", "Score", "Projected", "Accuracy", "Result"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[9px] font-black uppercase tracking-widest"
                    style={{ color: "#8b949e" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stats.recentSlates.map((s, i) => {
                const accuracy = ((s.score / s.proj) * 100).toFixed(1);
                const accuracyNum = parseFloat(accuracy);
                return (
                  <tr key={i} style={{ borderBottom: "1px solid #21262d" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "#1c2128")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                    <td className="px-4 py-3 text-sm font-bold text-white">{s.date}</td>
                    <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{s.place}</td>
                    <td className="px-4 py-3 font-black" style={{ color: sport.color }}>{s.score.toFixed(1)}</td>
                    <td className="px-4 py-3 text-sm" style={{ color: "#8b949e" }}>{s.proj.toFixed(1)}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-black px-2 py-0.5 rounded"
                        style={{
                          background: accuracyNum >= 100 ? "rgba(0,220,130,0.15)" : "rgba(248,81,73,0.1)",
                          color: accuracyNum >= 100 ? "#00dc82" : "#f85149",
                        }}>
                        {accuracy}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] font-black px-2 py-1 rounded uppercase tracking-wider"
                        style={{
                          background: s.cash ? "rgba(0,220,130,0.15)" : "rgba(248,81,73,0.1)",
                          color: s.cash ? "#00dc82" : "#f85149",
                        }}>
                        {s.cash ? "✓ Cashed" : "✗ Miss"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ── MODEL ACCURACY BY POSITION ── */}
        <div className="rounded-2xl p-5" style={{ background: "#161b22", border: "1px solid #30363d" }}>
          <h2 className="font-black text-sm text-white mb-4">ML Model Accuracy by Metric</h2>
          <div className="space-y-3">
            {[
              { label: "Projection Accuracy", value: 84 },
              { label: "Ownership Prediction", value: 71 },
              { label: "Ceiling Accuracy", value: 78 },
              { label: "Floor Accuracy", value: 88 },
              { label: "Vegas Odds Correlation", value: 92 },
            ].map(({ label, value }) => (
              <div key={label}>
                <div className="flex justify-between mb-1.5">
                  <span className="text-xs" style={{ color: "#c9d1d9" }}>{label}</span>
                  <span className="text-xs font-black" style={{ color: sport.color }}>{value}%</span>
                </div>
                <div className="h-2 rounded-full" style={{ background: "#21262d" }}>
                  <div className="h-2 rounded-full transition-all duration-700"
                    style={{ width: `${value}%`, background: `linear-gradient(90deg, ${sport.color}88, ${sport.color})` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
