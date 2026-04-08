"use client";

import { useState } from "react";
import Link from "next/link";

const SPORTS = [
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

const LIVE_GAMES = [
  {
    sport: "NFL",
    quarter: "Q3 04:12",
    home: "KC Chiefs",
    away: "LV Raiders",
    homeScore: 24,
    awayScore: 17,
    spread: "-7.5",
    total: "O 44.5",
    money: "-340",
    color: "#d4ac0d",
  },
  {
    sport: "NBA",
    quarter: "Q2 08:45",
    home: "LA Lakers",
    away: "GS Warriors",
    homeScore: 48,
    awayScore: 52,
    spread: "+2.5",
    total: "U 224",
    money: "+115",
    color: "#f97316",
  },
  {
    sport: "MLB",
    quarter: "7th Inn",
    home: "NY Yankees",
    away: "Boston Red Sox",
    homeScore: 4,
    awayScore: 3,
    spread: "-1.5",
    total: "O 8.5",
    money: "-180",
    color: "#3b82f6",
  },
];

const UPCOMING = [
  { time: "TONIGHT • 8:15 PM", matchup: "DAL Cowboys @ NY Giants",   sport: "NFL", odds: ["-110", "+110"] },
  { time: "TONIGHT • 10:00 PM", matchup: "PHX Suns @ GS Warriors",    sport: "NBA", odds: ["-155", "+130"] },
  { time: "TOMORROW • 1:05 PM", matchup: "Chicago Cubs @ LA Dodgers", sport: "MLB", odds: ["+145", "-165"] },
  { time: "TOMORROW • 7:30 PM", matchup: "Toronto Maple Leafs @ BOS", sport: "NHL", odds: ["+120", "-140"] },
];

const PARLAYS = [
  {
    tag: "🔥 TRENDING 3-LEGGER",
    odds: "+550",
    legs: ["Bills Moneyline", "Josh Allen O 1.5 TD", "Stefon Diggs O 75.5 Rec Yds"],
  },
  {
    tag: "⚡ AI OPTIMIZER PICK",
    odds: "+320",
    legs: ["Lakers -5.5", "LeBron O 28.5 Pts", "Under 224.5"],
  },
];

export default function LandingPage() {
  const [activeSport, setActiveSport] = useState("nfl");

  return (
    <div className="min-h-screen bg-[#0d1117] text-white font-sans">
      {/* ── HEADER ─────────────────────────────── */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-4 py-3"
        style={{ background: "rgba(13,17,23,0.96)", backdropFilter: "blur(12px)", borderBottom: "1px solid #30363d" }}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg font-black"
            style={{ background: "linear-gradient(135deg, #00dc82, #00b368)" }}>
            S
          </div>
          <span className="text-lg font-black italic tracking-tight"
            style={{ color: "#00dc82", fontStyle: "italic" }}>
            SPORTBOOK ME
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/dashboard"
            className="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
            style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82", border: "1px solid rgba(0,220,130,0.3)" }}>
            Dashboard
          </Link>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-bold"
            style={{ background: "#161b22", border: "1px solid #30363d" }}>
            <span className="text-xs" style={{ color: "#8b949e" }}>💰</span>
            <span style={{ color: "#00dc82" }}>$1,250.00</span>
          </div>
        </div>
      </header>

      {/* ── HERO BANNER ─────────────────────────── */}
      <section className="relative overflow-hidden mx-3 mt-3 rounded-2xl"
        style={{ minHeight: 220, background: "linear-gradient(135deg, #111827 0%, #1a2744 60%, #0f172a 100%)" }}>
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: "radial-gradient(circle at 70% 50%, rgba(0,220,130,0.3) 0%, transparent 60%), radial-gradient(circle at 20% 80%, rgba(212,172,13,0.2) 0%, transparent 50%)",
          }} />
        <div className="absolute inset-0" style={{ background: "url('data:image/svg+xml,%3Csvg width=\"60\" height=\"60\" viewBox=\"0 0 60 60\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cg fill=\"none\" fill-rule=\"evenodd\"%3E%3Cg fill=\"%2300dc82\" fill-opacity=\"0.03\"%3E%3Cpath d=\"M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')" }} />

        <div className="relative z-10 p-6 flex flex-col justify-center" style={{ minHeight: 220 }}>
          <div className="text-xs font-bold uppercase tracking-widest mb-2 px-2 py-1 rounded w-fit"
            style={{ background: "rgba(0,220,130,0.2)", color: "#00dc82" }}>
            EXCLUSIVE BONUS
          </div>
          <h1 className="text-3xl md:text-5xl font-black italic uppercase leading-tight mb-2">
            DFS SEASON<br />
            <span style={{ color: "#00dc82" }}>KICKOFF BOOST</span>
          </h1>
          <p className="text-sm md:text-base mb-5" style={{ color: "#8b949e" }}>
            Get +200% ROI Boost on all lineups this week.
          </p>
          <Link href="/optimizer"
            className="w-fit px-7 py-3 rounded-xl text-sm font-black uppercase tracking-wider transition-all hover:scale-105 hover:shadow-lg"
            style={{ background: "#00dc82", color: "#0d1117", boxShadow: "0 4px 20px rgba(0,220,130,0.4)" }}>
            BUILD LINEUPS NOW
          </Link>
        </div>

        {/* Decorative large number */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[120px] font-black italic opacity-5 select-none">
          DFS
        </div>
      </section>

      {/* ── TOP SPORTS ──────────────────────────── */}
      <section className="px-4 mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-black uppercase tracking-wider">Top Sports</h2>
          <button className="text-xs font-semibold" style={{ color: "#00dc82" }}>VIEW ALL</button>
        </div>

        <div className="flex gap-3 overflow-x-auto scroll-hide pb-2">
          {SPORTS.map((sport) => {
            const isActive = activeSport === sport.id;
            return (
              <button
                key={sport.id}
                onClick={() => setActiveSport(sport.id)}
                className="flex flex-col items-center gap-1.5 flex-shrink-0 transition-all duration-200"
              >
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl transition-all duration-200"
                  style={{
                    background: isActive ? "#00dc82" : "#161b22",
                    border: isActive ? "none" : "1px solid #30363d",
                    boxShadow: isActive ? "0 0 20px rgba(0,220,130,0.4)" : "none",
                    transform: isActive ? "scale(1.05)" : "scale(1)",
                  }}
                >
                  {sport.emoji}
                </div>
                <span
                  className="text-[10px] font-black tracking-widest uppercase"
                  style={{ color: isActive ? "#00dc82" : "#8b949e" }}
                >
                  {sport.label}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* ── LIVE NOW ────────────────────────────── */}
      <section className="px-4 mt-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-base font-black uppercase tracking-wider">Live Now</h2>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full"
            style={{ background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)" }}>
            <div className="live-dot" />
            <span className="text-[10px] font-black text-red-400 uppercase tracking-wider">LIVE</span>
          </div>
        </div>

        <div className="flex gap-3 overflow-x-auto scroll-hide pb-2">
          {LIVE_GAMES.map((game, i) => (
            <div key={i} className="flex-shrink-0 w-72 rounded-2xl overflow-hidden"
              style={{ background: "#161b22", border: "1px solid #30363d" }}>
              {/* Card top accent */}
              <div className="h-1 w-full" style={{ background: game.color }} />

              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded"
                    style={{ background: `${game.color}22`, color: game.color }}>
                    {game.sport} • {game.quarter}
                  </span>
                  <button className="text-muted-foreground hover:text-white transition-colors">⋯</button>
                </div>

                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-full" style={{ background: `${game.color}33`, border: `1px solid ${game.color}55` }} />
                      <span className="font-semibold text-sm">{game.home}</span>
                    </div>
                    <span className="text-2xl font-black" style={{ color: game.color }}>{game.homeScore}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-full" style={{ background: "#21262d", border: "1px solid #30363d" }} />
                      <span className="font-semibold text-sm">{game.away}</span>
                    </div>
                    <span className="text-2xl font-black" style={{ color: "#8b949e" }}>{game.awayScore}</span>
                  </div>
                </div>

                {/* Odds row */}
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "SPREAD", value: game.spread },
                    { label: "TOTAL", value: game.total },
                    { label: "MONEY", value: game.money },
                  ].map((o) => (
                    <div key={o.label} className="rounded-lg p-2 text-center cursor-pointer transition-all hover:border-[#00dc82]"
                      style={{ background: "#0d1117", border: "1px solid #30363d" }}>
                      <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "#8b949e" }}>
                        {o.label}
                      </div>
                      <div className="text-sm font-black" style={{ color: "#00dc82" }}>{o.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── POPULAR PARLAYS ─────────────────────── */}
      <section className="px-4 mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-black uppercase tracking-wider">Popular Parlays</h2>
          <button className="text-xs font-semibold" style={{ color: "#00dc82" }}>SEE MORE</button>
        </div>

        <div className="space-y-3">
          {PARLAYS.map((p, i) => (
            <div key={i} className="rounded-2xl overflow-hidden"
              style={{ background: "#161b22", border: "1px solid #30363d", borderLeft: "3px solid #00dc82" }}>
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-black">{p.tag}</span>
                  <span className="text-lg font-black" style={{ color: "#00dc82" }}>{p.odds}</span>
                </div>
                <div className="space-y-1.5 mb-4">
                  {p.legs.map((leg, j) => (
                    <div key={j} className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ background: "rgba(0,220,130,0.2)", border: "1px solid rgba(0,220,130,0.4)" }}>
                        <span className="text-[8px]" style={{ color: "#00dc82" }}>✓</span>
                      </div>
                      <span className="text-sm" style={{ color: "#c9d1d9" }}>{leg}</span>
                    </div>
                  ))}
                </div>
                <button className="w-full py-2.5 rounded-xl text-sm font-black uppercase tracking-wider transition-all hover:opacity-90"
                  style={{ background: "rgba(0,220,130,0.15)", color: "#00dc82", border: "1px solid rgba(0,220,130,0.3)" }}>
                  ADD TO LINEUP
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── QUICK PICKS ─────────────────────────── */}
      <section className="px-4 mt-6">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl p-4" style={{ background: "#161b22", border: "1px solid #30363d" }}>
            <div className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color: "#8b949e" }}>QUICK PICKS</div>
            <div className="font-black text-sm leading-tight mb-2">Monday Night Double</div>
            <div className="text-2xl font-black" style={{ color: "#00dc82" }}>+320</div>
            <button className="mt-3 w-8 h-8 rounded-lg flex items-center justify-center font-bold text-lg"
              style={{ background: "rgba(0,220,130,0.2)", color: "#00dc82", border: "1px solid rgba(0,220,130,0.3)" }}>
              +
            </button>
          </div>
          <div className="rounded-2xl p-4" style={{ background: "#161b22", border: "1px solid #30363d" }}>
            <div className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color: "#8b949e" }}>LIVE BOOST</div>
            <div className="font-black text-sm leading-tight mb-2">Anytime TD Scorer</div>
            <div className="text-2xl font-black" style={{ color: "#00dc82" }}>+1200</div>
            <button className="mt-3 w-8 h-8 rounded-lg flex items-center justify-center font-bold text-lg"
              style={{ background: "rgba(0,220,130,0.2)", color: "#00dc82", border: "1px solid rgba(0,220,130,0.3)" }}>
              +
            </button>
          </div>
        </div>
      </section>

      {/* ── COMING UP ───────────────────────────── */}
      <section className="px-4 mt-6 mb-28">
        <h2 className="text-base font-black uppercase tracking-wider mb-3">Coming Up</h2>
        <div className="rounded-2xl overflow-hidden" style={{ background: "#161b22", border: "1px solid #30363d" }}>
          {UPCOMING.map((g, i) => {
            const sportObj = SPORTS.find(s => s.id === g.sport.toLowerCase());
            return (
              <div key={i} className="flex items-center justify-between px-4 py-3"
                style={{ borderBottom: i < UPCOMING.length - 1 ? "1px solid #21262d" : "none" }}>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: sportObj?.color || "#8b949e" }}>
                    {g.sport} • {g.time}
                  </div>
                  <div className="text-sm font-semibold">{g.matchup}</div>
                </div>
                <div className="flex gap-2 ml-3 flex-shrink-0">
                  {g.odds.map((odd, j) => (
                    <button key={j} className="odds-pill">{odd}</button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── FLOATING ACTION BUTTON ──────────────── */}
      <Link href="/optimizer" className="fab" aria-label="Open lineup optimizer">
        +
      </Link>

      {/* ── BOTTOM NAVIGATION ───────────────────── */}
      <nav className="fixed bottom-0 left-0 right-0 z-50"
        style={{ background: "rgba(13,17,23,0.97)", backdropFilter: "blur(12px)", borderTop: "1px solid #30363d" }}>
        <div className="flex items-center justify-around py-2 pb-safe">
          {[
            { href: "/",          icon: "🏠", label: "Home",    active: true  },
            { href: "/dashboard", icon: "📊", label: "Sports",  active: false },
            { href: "/optimizer", icon: "📋", label: "My Bets", active: false, badge: true },
            { href: "/billing",   icon: "👤", label: "Account", active: false },
          ].map((item) => (
            <Link key={item.href} href={item.href}
              className="flex flex-col items-center gap-1 relative py-1 px-3 transition-all">
              <div className="relative">
                <span className="text-xl">{item.icon}</span>
                {item.badge && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full"
                    style={{ background: "#00dc82" }} />
                )}
              </div>
              <span className="text-[10px] font-black uppercase tracking-wider"
                style={{ color: item.active ? "#00dc82" : "#8b949e" }}>
                {item.label}
              </span>
            </Link>
          ))}
        </div>
      </nav>
    </div>
  );
}
