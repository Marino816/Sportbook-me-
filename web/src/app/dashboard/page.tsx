"use client";

import { Activity, AlertTriangle, Calendar, CheckCircle2, Save, XCircle } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { checkHealth, fetchProjections, fetchPerformanceStats } from "@/lib/api";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

const SPORTS = [
  { id: "all",    label: "All",    emoji: "🎯", color: "#00dc82" },
  { id: "nfl",    label: "NFL",    emoji: "🏈", color: "#d4ac0d" },
  { id: "nba",    label: "NBA",    emoji: "🏀", color: "#f97316" },
  { id: "mlb",    label: "MLB",    emoji: "⚾", color: "#3b82f6" },
  { id: "nhl",    label: "NHL",    emoji: "🏒", color: "#06b6d4" },
  { id: "soccer", label: "SOCCER", emoji: "⚽", color: "#22c55e" },
  { id: "mls",    label: "MLS",    emoji: "🥅", color: "#0ea5e9" },
  { id: "ufc",    label: "UFC",    emoji: "🥊", color: "#ef4444" },
  { id: "pga",    label: "PGA",    emoji: "⛳", color: "#10b981" },
  { id: "ncaaf",  label: "NCAAF",  emoji: "🏟️", color: "#a855f7" },
  { id: "ncaam",  label: "NCAAM",  emoji: "🏀", color: "#6366f1" },
  { id: "ncaaw",  label: "NCAAW",  emoji: "🏀", color: "#ec4899" },
  { id: "boxing", label: "BOXING", emoji: "🥋", color: "#f59e0b" },
];

const ALL_SLATES = [
  { sport: "NBA", sportId: "nba",  time: "7:00 PM EST", games: 6,  site: "DraftKings", color: "#f97316" },
  { sport: "NBA", sportId: "nba",  time: "7:30 PM EST", games: 4,  site: "FanDuel",    color: "#f97316" },
  { sport: "MLB", sportId: "mlb",  time: "1:05 PM EST", games: 15, site: "DraftKings", color: "#3b82f6" },
  { sport: "NFL", sportId: "nfl",  time: "1:00 PM EST", games: 8,  site: "DraftKings", color: "#d4ac0d" },
  { sport: "NHL", sportId: "nhl",  time: "7:00 PM EST", games: 5,  site: "FanDuel",    color: "#06b6d4" },
  { sport: "PGA", sportId: "pga",  time: "12:00 PM EST",games: 1,  site: "DraftKings", color: "#10b981" },
  { sport: "UFC", sportId: "ufc",  time: "10:00 PM EST",games: 3,  site: "DraftKings", color: "#ef4444" },
  { sport: "MLS", sportId: "mls",  time: "8:00 PM EST", games: 4,  site: "FanDuel",    color: "#0ea5e9" },
];

function DashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSport = searchParams.get("sport") || "all";

  const { data: isApiConnected, isLoading: isHealthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30000,
  });

  const { data: perf } = useQuery({
    queryKey: ['performance'],
    queryFn: fetchPerformanceStats,
  });

  const { data: projections } = useQuery({
    queryKey: ['projections', 1],
    queryFn: () => fetchProjections(1),
  });

  const apiStatus = isHealthLoading ? "Checking..." : isApiConnected ? "API Connected" : "API Offline";

  const filteredSlates = activeSport === "all"
    ? ALL_SLATES
    : ALL_SLATES.filter(s => s.sportId === activeSport);

  const setActiveSport = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("sport", id);
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <div className="flex-1 overflow-y-auto h-full" style={{ background: "#0d1117" }}>

      {/* ── TOP BAR ────────────────────────────── */}
      <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "#30363d" }}>
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Dashboard</h1>
          <p className="text-sm mt-0.5" style={{ color: "#8b949e" }}>
            Your DFS command center — {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold border ${
          isApiConnected
            ? "text-emerald-400 border-emerald-500/30"
            : "text-red-400 border-red-500/30"
          }`}
          style={{ background: isApiConnected ? "rgba(0,220,130,0.1)" : "rgba(239,68,68,0.1)" }}>
          {isApiConnected ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
          {apiStatus}
        </div>
      </div>

      {/* ── SPORT FILTER BAR ───────────────────── */}
      <div className="px-4 pt-4">
        <div className="flex gap-2 overflow-x-auto scroll-hide pb-2">
          {SPORTS.map((sport) => {
            const isActive = activeSport === sport.id;
            return (
              <button
                key={sport.id}
                onClick={() => setActiveSport(sport.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-black uppercase tracking-wider whitespace-nowrap transition-all duration-150 flex-shrink-0"
                style={{
                  background: isActive ? sport.color : "#161b22",
                  color: isActive ? "#0d1117" : "#8b949e",
                  border: isActive ? `1px solid ${sport.color}` : "1px solid #30363d",
                  boxShadow: isActive ? `0 0 12px ${sport.color}44` : "none",
                }}
              >
                <span>{sport.emoji}</span>
                <span>{sport.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-6 space-y-6">

        {/* ── KPI CARDS ──────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            title="Active Players"
            value={projections?.data?.length || 0}
            icon={Calendar}
            trend="Data Fetched Live"
          />
          <KpiCard
            title="Projected Edge"
            value={perf?.data?.total_roi || "0%"}
            icon={Activity}
            trend={perf?.data?.ave_error ? `MAE: ${perf.data.ave_error}` : "Calculating..."}
          />
          <KpiCard
            title="Win Rate"
            value={perf?.data?.win_rate || "0%"}
            icon={Save}
            trend="Historical performance"
          />
          <KpiCard title="Active Alerts" value="3" icon={AlertTriangle} trend="Critical injuries" destructive />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── SLATES ─────────────────────────────── */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl overflow-hidden" style={{ background: "#161b22", border: "1px solid #30363d" }}>
              <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "#30363d" }}>
                <h2 className="font-black text-base">
                  {activeSport === "all" ? "All Slates Today" : `${SPORTS.find(s => s.id === activeSport)?.label} Slates`}
                </h2>
                <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82" }}>
                  {filteredSlates.length} available
                </span>
              </div>

              <div className="p-4 space-y-3">
                {filteredSlates.length === 0 ? (
                  <div className="text-center py-8" style={{ color: "#8b949e" }}>
                    <p className="text-2xl mb-2">🏟️</p>
                    <p className="text-sm font-medium">No slates available for this sport today.</p>
                  </div>
                ) : (
                  filteredSlates.map((slate, i) => (
                    <SlateCard key={i} {...slate} />
                  ))
                )}
              </div>

              <div className="px-5 py-3 border-t" style={{ borderColor: "#30363d" }}>
                <Link href="/optimizer" className="text-sm font-bold hover:opacity-80 transition-opacity flex items-center gap-1"
                  style={{ color: "#00dc82" }}>
                  Go to Optimizer →
                </Link>
              </div>
            </div>

            {/* ROI Snapshot */}
            <div className="rounded-2xl flex flex-col items-center justify-center relative overflow-hidden"
              style={{ background: "#161b22", border: "1px solid #30363d", minHeight: 160 }}>
              <div className="absolute inset-0 opacity-10"
                style={{ background: "radial-gradient(ellipse at center, rgba(0,220,130,0.4) 0%, transparent 70%)" }} />
              <Activity className="size-7 mb-2" style={{ color: "#00dc82" }} />
              <h3 className="font-black text-2xl">{perf?.data?.total_roi || "+0.0%"} ROI</h3>
              <p className="text-sm text-center max-w-xs mt-1.5" style={{ color: "#8b949e" }}>
                Bankroll up across last 30 slates. {perf?.data?.win_rate || "0%"} win rate sustained.
              </p>
            </div>
          </div>

          {/* ── NEWS FEED ──────────────────────────── */}
          <div className="space-y-4">
            <div className="rounded-2xl h-full" style={{ background: "#161b22", border: "1px solid #30363d" }}>
              <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: "#30363d" }}>
                <AlertTriangle className="size-4 text-amber-500" />
                <h2 className="font-black text-base">Live News</h2>
                <div className="ml-auto live-dot" />
              </div>
              <div className="p-4 space-y-4">
                <NewsItem time="10m ago" text="LeBron James (LAL) listed as QUESTIONABLE for tonight." impact="negative" />
                <NewsItem time="1h ago" text="Anthony Davis (LAL) upgraded to PROBABLE." impact="positive" />
                <NewsItem time="2h ago" text="Vegas line on LAL vs GSW moved to 238.5 (+2.0)." impact="neutral" />
                <NewsItem time="3h ago" text="Patrick Mahomes cleared — no injury designation." impact="positive" />
                <NewsItem time="4h ago" text="NHL: Connor McDavid game-time decision vs TOR." impact="negative" />
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function KpiCard({ title, value, icon: Icon, trend, destructive }: any) {
  return (
    <div className="rounded-2xl p-5 flex flex-col"
      style={{ background: "#161b22", border: "1px solid #30363d" }}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: "#8b949e" }}>{title}</h3>
        <div className="p-2 rounded-xl"
          style={{
            background: destructive ? "rgba(239,68,68,0.15)" : "rgba(0,220,130,0.15)",
            color: destructive ? "#f85149" : "#00dc82",
          }}>
          <Icon className="size-4" />
        </div>
      </div>
      <div className="text-3xl font-black mb-1">{value}</div>
      <div className="text-xs" style={{ color: destructive ? "#f85149" : "#8b949e" }}>{trend}</div>
    </div>
  );
}

function SlateCard({ sport, time, games, site, color }: any) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl cursor-pointer transition-all hover:border-opacity-60"
      style={{ background: "#0d1117", border: "1px solid #30363d" }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = color)}
      onMouseLeave={e => (e.currentTarget.style.borderColor = "#30363d")}
    >
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl flex items-center justify-center font-black text-sm"
          style={{ background: `${color}22`, color: color, border: `1px solid ${color}33` }}>
          {sport}
        </div>
        <div>
          <div className="font-bold text-sm text-white">{site} Main Slate</div>
          <div className="text-xs mt-0.5" style={{ color: "#8b949e" }}>{time} • {games} Games</div>
        </div>
      </div>
      <button className="px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all hover:opacity-90"
        style={{ background: "#00dc82", color: "#0d1117", boxShadow: "0 2px 10px rgba(0,220,130,0.3)" }}>
        Load
      </button>
    </div>
  );
}

function NewsItem({ time, text, impact }: any) {
  const dotColor = impact === "negative" ? "#f85149" : impact === "positive" ? "#00dc82" : "#3b82f6";
  return (
    <div className="flex gap-3 pb-4 border-b last:border-0 last:pb-0" style={{ borderColor: "#21262d" }}>
      <div className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: dotColor }} />
      <div>
        <p className="text-sm leading-snug" style={{ color: "#c9d1d9" }}>{text}</p>
        <span className="text-[10px] mt-1 block font-medium" style={{ color: "#8b949e" }}>{time}</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center" style={{ background: "#0d1117" }}>
      <div className="text-sm" style={{ color: "#8b949e" }}>Loading...</div>
    </div>}>
      <DashboardInner />
    </Suspense>
  );
}
