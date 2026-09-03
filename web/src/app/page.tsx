"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  TrendingUp, Activity, Target, Layers, Bot, Sparkles,
  Users, BarChart3, Brain, Menu, X, ChevronRight, Check,
  ArrowRight, Zap, Star, Swords, Building2, Trophy, Flame, Shield, Radio, GitCompare,
} from "lucide-react";
import { SBMEBackground } from "@/components/sbme-background";
import { ROOKIE_LEAGUES, SOCCER_LEAGUE_IDS } from "@/lib/sgo-leagues";

/* ── Brand palette ── */
const navy = "#0a0f24";
const cardBg = "#0a0f24";
const cardElevated = "#10162f";
const gold = "#c9a84c";
const goldDim = "#a68a32";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#8b9cb3";

/* ── Shared button styles ── */
function GoldButton({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <Link href={href}
      className={`inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl font-bold text-sm tracking-wide
        hover:brightness-110 transition-all duration-200 shadow-[0_4px_24px_rgba(201,168,76,0.35)] ${className}`}
      style={{ background: gold, color: navy }}>
      {children}
    </Link>
  );
}

function GhostButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href}
      className="inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl font-bold text-sm tracking-wide
        transition-all duration-200 hover:border-[#c9a84c] hover:text-[#c9a84c]"
      style={{ border: `1px solid ${border}`, color: textSecondary }}>
      {children}
    </Link>
  );
}

/* ── Sparkline SVG ── */
function Sparkline({ data, width = 80, height = 24, stroke }: { data: number[]; width?: number; height?: number; stroke: string }) {
  if (!data.length) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - 2) + 1;
    const y = height - 2 - ((v - min) / range) * (height - 4);
    return `${x},${y}`;
  });
  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline points={points.join(" ")} fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── Mini bar chart ── */
function MiniBarChart({ values, width = 60, height = 32 }: { values: number[]; width?: number; height?: number }) {
  const max = Math.max(...values, 1);
  const barW = Math.max(2, (width - values.length * 2) / values.length);
  return (
    <svg width={width} height={height} className="shrink-0">
      {values.map((v, i) => {
        const h = Math.max(2, (v / max) * (height - 2));
        return (
          <rect key={i} x={i * (barW + 2)} y={height - h} width={barW} height={h}
            rx="1" fill={v >= max * 0.8 ? gold : "#334155"} />
        );
      })}
    </svg>
  );
}

/* ── Section wrapper ── */
function Section({ id, className = "", children }: { id?: string; className?: string; children: React.ReactNode }) {
  return (
    <section id={id} className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ${className}`}>
      {children}
    </section>
  );
}

/* ── Parlay capability item ── */
function ParlayCapability({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex gap-4 p-5 rounded-2xl border transition-all hover:border-[#c9a84c30]"
      style={{ background: cardElevated, borderColor: border }}>
      <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${gold}10`, border: `1px solid ${gold}15` }}>
        {icon}
      </div>
      <div>
        <h4 className="text-sm font-extrabold mb-1" style={{ color: textPrimary }}>{title}</h4>
        <p className="text-[13px] leading-relaxed" style={{ color: textSecondary }}>{description}</p>
      </div>
    </div>
  );
}

/* ── Bookmaker name pill (IP-safe: text only, no logos) ── */
function BookPill({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold shrink-0"
      style={{ background: cardElevated, border: `1px solid ${border}`, color: textSecondary }}>
      <span style={{ color: gold, fontSize: 9 }}>●</span>
      {name}
    </span>
  );
}

/* ── Parlay Example Card (IP-safe: text names only, no logos) ── */
function ParlayDemoCard() {
  const legs = [
    { event: "NYY @ LAD", market: "Moneyline", pick: "NYY ML", odds: "+145", result: true },
    { event: "BOS @ HOU", market: "Run Line", pick: "BOS +1.5", odds: "-110", result: true },
    { event: "CHC @ STL", market: "Total", pick: "Over 8.5", odds: "-105", result: true },
    { event: "ATL @ NYM", market: "Player Prop", pick: "R. Acuna O 1.5 H+R+RBI", odds: "-120", result: null },
  ];

  const multiOdds = legs.reduce((acc, l) => { const o = Number(l.odds); return acc * (o > 0 ? 1 + o / 100 : 1 + 100 / Math.abs(o)); }, 1);
  const payout = Math.round(multiOdds * 100 - 100);

  return (
    <div className="rounded-3xl border overflow-hidden shadow-2xl" style={{ background: cardElevated, borderColor: border }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: border }}>
        <div className="flex items-center gap-2.5">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={gold} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
          </svg>
          <span className="text-xs font-extrabold tracking-widest" style={{ color: gold }}>YOUR PARLAY</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md" style={{ background: `${gold}12`, color: gold }}>4-LEG</span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md" style={{ background: "#4ade8012", color: "#4ade80" }}>EXAMPLE — NOT LIVE DATA</span>
        </div>
      </div>

      {/* Legs */}
      <div className="px-5 py-3 space-y-2">
        {legs.map((leg, i) => (
          <div key={i} className="flex items-center gap-3 py-2.5 px-3 rounded-xl border transition-all"
            style={{
              background: leg.result === true ? "rgba(74,222,128,0.04)" : leg.result === false ? "rgba(248,113,113,0.04)" : "rgba(255,255,255,0.01)",
              borderColor: leg.result === true ? "rgba(74,222,128,0.15)" : leg.result === false ? "rgba(248,113,113,0.15)" : border,
            }}>
            {/* Result icon */}
            <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
              style={{ background: leg.result === true ? "rgba(74,222,128,0.15)" : leg.result === false ? "rgba(248,113,113,0.15)" : "rgba(255,255,255,0.05)" }}>
              {leg.result === true ? <Check size={11} style={{ color: "#4ade80" }} /> :
               leg.result === false ? <X size={11} style={{ color: "#f87171" }} /> :
               <span className="text-[9px] font-bold" style={{ color: textMuted }}>{i + 1}</span>}
            </div>
            {/* Leg details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-bold" style={{ color: textMuted }}>{leg.market}</span>
                <span className="text-[10px]" style={{ color: textMuted }}>·</span>
                <span className="text-[10px] font-semibold truncate" style={{ color: textPrimary }}>{leg.event}</span>
              </div>
              <div className="text-xs font-bold" style={{ color: textSecondary }}>{leg.pick}</div>
            </div>
            {/* Odds */}
            <span className="text-sm font-extrabold shrink-0" style={{ color: gold }}>{leg.odds}</span>
          </div>
        ))}
      </div>

      {/* Footer — payout */}
      <div className="px-5 py-3.5 border-t flex items-center justify-between" style={{ borderColor: border, background: "rgba(10,15,36,0.5)" }}>
        <div>
          <div className="text-[10px] font-bold tracking-wider uppercase" style={{ color: textMuted }}>4-Leg Multiplier</div>
          <div className="text-xs" style={{ color: textMuted }}>{(multiOdds * 100).toFixed(0)} &times; $100</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-bold tracking-wider uppercase" style={{ color: textMuted }}>Potential Payout</div>
          <div className="text-lg font-extrabold" style={{ color: "#4ade80" }}>+${payout}</div>
        </div>
      </div>
    </div>
  );
}

function IntelligenceDemoCard() {
  const sports = ["MLB", "NFL", "NBA", "NHL", "EPL", "UCL", "MLS"];
  const rows = [
    { n: "C. Sale", p: "P", sal: "$9,600", proj: 36.5, fppg: 38.0, ceil: 52.0, own: "18.4%", lev: 2.1 },
    { n: "L. Gilbert", p: "P", sal: "$9,800", proj: 34.5, fppg: 35.2, ceil: 48.0, own: "14.2%", lev: 1.6 },
    { n: "F. Freeman", p: "1B", sal: "$5,400", proj: 16.8, fppg: 31.1, ceil: 28.0, own: "22.7%", lev: -0.8 },
    { n: "T. Stephenson", p: "C", sal: "$3,600", proj: 13.7, fppg: 38.1, ceil: 24.0, own: "8.1%", lev: 3.4 },
    { n: "C. Seager", p: "SS", sal: "$4,600", proj: 11.8, fppg: 25.7, ceil: 20.0, own: "12.3%", lev: 1.1 },
  ];

  return (
    <div className="sbme-intel">
      <div className="sbme-intel-glow" />
      <div className="sbme-intel-shell">
        <div className="sbme-intel-cut" />
        <div className="sbme-intel-bracket sbme-intel-bracket--tl" />
        <div className="sbme-intel-bracket sbme-intel-bracket--br" />
        <div className="sbme-intel-grid" />

        <div className="sbme-intel-header">
          <div className="sbme-intel-brand">
            <div className="live-dot" />
            <span>SB ME INTELLIGENCE&trade;</span>
            <div className="sbme-intel-dots" aria-hidden>
              <i /><i /><i />
            </div>
          </div>
          <span className="sbme-intel-badge">INTERFACE DEMO</span>
        </div>

        <div className="sbme-intel-tabs scroll-hide">
          {sports.map((s, i) => (
            <span key={s} className={`sbme-intel-tab${i === 0 ? " is-on" : ""}`}>{s}</span>
          ))}
        </div>

        <div className="sbme-intel-intro">
          <h3>
            One Platform. Your Data.<br />
            <span style={{ color: gold }}>Smarter Lineups &amp; Sports Analysis.</span>
          </h3>
          <p>
            Real-time DFS data, SB ME projections, lineup optimization, simulations, stacks, player research, and sportsbook market analysis — built into one intelligence platform.
          </p>
        </div>

        <div className="sbme-intel-panel">
          <div className="sbme-intel-panel-label">DFS Optimizer Preview</div>
          <div className="sbme-intel-table">
            <div className="sbme-intel-row sbme-intel-row--head">
              {["PLAYER", "SALARY", "SB PROJ.", "FPPG", "CEILING", "OWN%", "LEV."].map((h) => (
                <span key={h}>{h}</span>
              ))}
            </div>
            {rows.map((r, i) => (
              <div key={r.n} className={`sbme-intel-row sbme-intel-row--data${i === 0 ? " is-lead" : ""}`}>
                <span><span className="sbme-intel-pos">{r.p}</span>{r.n}</span>
                <span className="sbme-intel-gold">{r.sal}</span>
                <span className="sbme-intel-gold">{r.proj}</span>
                <span>{r.fppg}</span>
                <span className="sbme-intel-up">{r.ceil}</span>
                <span className="sbme-intel-muted">{r.own}</span>
                <span className={r.lev >= 0 ? "sbme-intel-up" : "sbme-intel-down"}>{r.lev > 0 ? "+" : ""}{r.lev}</span>
              </div>
            ))}
          </div>
          <p className="sbme-intel-note">
            &uarr; Interface demonstration. Values shown are illustrative, not live data.
          </p>
        </div>

        <div className="sbme-intel-actions">
          <Link href="/optimizer" className="sbme-intel-btn sbme-intel-btn-primary">BUILD A LINEUP</Link>
          <Link href="/market-tools" className="sbme-intel-btn sbme-intel-btn-secondary">EXPLORE MARKET TOOLS</Link>
        </div>
      </div>
    </div>
  );
}

/* ── MAIN PAGE ── */
export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = [
    { label: "Features", href: "#features" },
    { label: "Parlay Builder", href: "#parlay" },
    { label: "Pricing", href: "#pricing" },
    { label: "Resources", href: "#resources" },
    { label: "About", href: "#about" },
  ];

  // Featured 20 bookmakers (text names only — IP-safe)
  const featuredBooks = [
    "DraftKings", "FanDuel", "BetMGM", "Caesars", "ESPN BET",
    "Bovada", "Bet365", "PointsBet", "BetRivers", "Pinnacle",
    "Unibet", "William Hill", "Barstool", "Betway", "Betfred",
    "Circa", "Hard Rock Bet", "BetOnline", "Polymarket", "Bally Bet",
  ];

  const coveredSports = ROOKIE_LEAGUES.map((lg) => ({
    name: lg.label,
    leagueID: lg.leagueID,
    sport: lg.sportID,
  }));
  const soccerLeagues = ROOKIE_LEAGUES.filter((lg) => SOCCER_LEAGUE_IDS.includes(lg.leagueID as typeof SOCCER_LEAGUE_IDS[number]));

  return (
    <SBMEBackground variant="hero" className="min-h-screen">
    <div style={{ color: textPrimary, fontFamily: "'Inter', sans-serif" }} className="min-h-screen overflow-x-hidden">

      {/* ═══ HEADER ═══ */}
      <header className="sticky top-0 z-50 border-b" style={{ background: "rgba(10,15,36,0.92)", backdropFilter: "blur(16px)", borderColor: border }}>
        <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
          {/* Logo */}
          <Link href="/" className="shrink-0">
            <Image src="/logo.png" alt="SB ME DFS.AI" width={110} height={58} priority />
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((l) => (
              <a key={l.label} href={l.href}
                className="px-3 py-2 rounded-lg text-sm font-semibold transition-colors duration-150"
                style={{ color: textSecondary }}
                onMouseEnter={(e) => (e.currentTarget.style.color = gold)}
                onMouseLeave={(e) => (e.currentTarget.style.color = textSecondary)}>
                {l.label}
              </a>
            ))}
          </nav>

          {/* Desktop auth */}
          <div className="hidden md:flex items-center gap-3">
            <Link href="/login"
              className="px-4 py-2.5 rounded-xl text-sm font-semibold border transition-all duration-200"
              style={{ borderColor: border, color: textSecondary }}>
              Log In
            </Link>
            <Link href="/register"
              className="px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200"
              style={{ background: gold, color: navy }}>
              Sign Up
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden p-2" style={{ color: textSecondary }}>
            {menuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t" style={{ borderColor: border, background: cardBg }}>
            <nav className="flex flex-col px-4 py-3 gap-2">
              {navLinks.map((l) => (
                <a key={l.label} href={l.href} onClick={() => setMenuOpen(false)}
                  className="py-2.5 text-sm font-semibold" style={{ color: textSecondary }}>
                  {l.label}
                </a>
              ))}
              <div className="flex gap-3 mt-3 pt-3 border-t" style={{ borderColor: border }}>
                <Link href="/login" onClick={() => setMenuOpen(false)}
                  className="flex-1 text-center py-2.5 rounded-xl text-sm font-semibold border"
                  style={{ borderColor: border, color: textSecondary }}>Log In</Link>
                <Link href="/register" onClick={() => setMenuOpen(false)}
                  className="flex-1 text-center py-2.5 rounded-xl text-sm font-bold"
                  style={{ background: gold, color: navy }}>Sign Up</Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* ═══ HERO ═══ */}
      <Section className="py-16 md:py-24 lg:py-28">
        <div className="relative grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left */}
          <div>
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs font-bold tracking-widest mb-6"
              style={{ borderColor: `${gold}40`, color: gold, background: `${gold}08` }}>
              <Sparkles size={13} /> SPORTBOOK ME DFS AI · SB ME
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1] mb-4" style={{ color: textPrimary }}>
              DFS Intelligence.<br />
              Live Markets.<br />
              <span style={{ color: gold }}>One AI Platform.</span>
            </h1>

            <p className="text-lg font-semibold mb-4" style={{ color: gold }}>
              Analytics, DFS optimization, and sports intelligence — not a sportsbook.
            </p>

            <p className="text-base max-w-lg mb-8" style={{ color: textSecondary }}>
              Projections, lineup optimization, live scores, multi-book market data, Fair Odds, Book Consensus, alternate lines, player and team props, and SB ME AI — across 17 supported leagues including soccer.
            </p>

            <div className="flex flex-wrap gap-4">
              <GoldButton href="/register">
                Get Started <ChevronRight size={16} />
              </GoldButton>
              <GhostButton href="#features">
                See How It Works <ArrowRight size={16} />
              </GhostButton>
            </div>
          </div>

          {/* Right — dashboard visual with athlete artwork */}
          <div className="relative">
            {/* ── Athlete silhouettes ── */}
            <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden" style={{ opacity: 0.12 }}>
              <svg width="100%" height="100%" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice" fill="none">
                {/* Basketball — top-left */}
                <g transform="translate(20, 30) scale(0.7)" stroke={gold} strokeWidth="3" fill="none" opacity="0.6">
                  <circle cx="40" cy="20" r="12" /><path d="M40 32v28 M28 50h24" />
                  <path d="M40 60l-18 35 M40 60l18 35 M40 38l-22-15 M40 38l22-15" /><circle cx="65" cy="12" r="8" />
                </g>
                {/* Football — bottom-left */}
                <g transform="translate(60, 270) scale(0.7)" stroke={gold} strokeWidth="3" fill="none" opacity="0.5">
                  <ellipse cx="30" cy="18" rx="14" ry="16" /><path d="M16 18l-8 6 M44 18l8 6" strokeWidth="4" />
                  <path d="M30 34v32 M30 42l-22-8 M30 42l22 10 M30 66l-20 32 M30 66l22 28" />
                </g>
                {/* Baseball — center-right */}
                <g transform="translate(280, 80) scale(0.7)" stroke={gold} strokeWidth="3" fill="none" opacity="0.6">
                  <ellipse cx="35" cy="16" rx="13" ry="9" /><path d="M22 16v-4" strokeWidth="4" />
                  <path d="M35 25v35 M35 32l30-22 M35 32l-18 8 M35 60l-18 35 M35 60l18 35" />
                  <line x1="65" y1="10" x2="82" y2="-5" strokeWidth="4" />
                </g>
                {/* Hockey — top-right */}
                <g transform="translate(300, 250) scale(0.7)" stroke={gold} strokeWidth="3" fill="none" opacity="0.5">
                  <circle cx="35" cy="18" r="11" /><path d="M35 29v32 M35 38l-24 6 M35 38l28 10 M35 61l-20 32 M35 61l22 28" />
                  <line x1="63" y1="48" x2="68" y2="82" strokeWidth="3" />
                </g>
              </svg>
            </div>

            <IntelligenceDemoCard />
          </div>
        </div>
      </Section>

      {/* ═══ FEATURE STRIP ═══ */}
      <div id="features" style={{ borderTop: `1px solid ${border}`, borderBottom: `1px solid ${border}`, background: "transparent" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {[
              { icon: Layers, title: "DFS Optimization", desc: "Projections, salary pipeline, and CP-SAT lineup optimization for supported DFS slates." },
              { icon: TrendingUp, title: "Market Intelligence", desc: "Multi-book lines, Fair Odds, and Book Consensus when SportsGameOdds returns them." },
              { icon: Bot, title: "SB ME AI", desc: "Ask about today's games, markets, props, scores, or DFS slate — from live SB ME data only." },
              { icon: Radio, title: "Live Scores & Markets", desc: "Upcoming, live, and final events with scores, status, and market freshness." },
              { icon: Target, title: "Props & Alternate Markets", desc: "Player props, team props, main lines, and alternate lines — never invented when missing." },
              { icon: GitCompare, title: "Bookmaker Comparison", desc: "Side-by-side prices for books that actually returned a market. Missing books stay empty." },
              { icon: Swords, title: "Parlay Intelligence", desc: "Plan multi-leg combinations with current lines, Fair Odds, and consensus context. Analytical only — SB ME does not place wagers." },
              { icon: Trophy, title: "Multi-League Coverage", desc: "17 Rookie leagues including Premier League, Champions League, MLS, La Liga, Bundesliga, Serie A, Ligue 1, and International Soccer." },
            ].map((f, i) => {
              const Icon = f.icon;
              return (
                <div key={i} className="text-center group rounded-2xl border p-4 sm:p-5"
                  style={{ background: "rgba(16,22,47,0.82)", borderColor: border }}>
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-3 transition-all duration-200 group-hover:scale-110"
                    style={{ background: `${gold}10`, border: `1px solid ${gold}18` }}>
                    <Icon size={22} style={{ color: gold }} />
                  </div>
                  <h3 className="text-sm font-bold mb-1.5" style={{ color: textPrimary }}>{f.title}</h3>
                  <p className="text-[13px] leading-relaxed" style={{ color: textSecondary }}>{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/*  PARLAY BUILDER SHOWCASE — MAJOR HOME PAGE FEATURE SECTION  */}
      {/* ═══════════════════════════════════════════════════════════ */}
      <div id="parlay" style={{ background: "transparent", borderBottom: `1px solid ${border}` }}>
        <Section className="py-20 md:py-24 lg:py-28">

          {/* ── Section Header ── */}
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs font-bold tracking-widest mb-6"
              style={{ borderColor: `${gold}40`, color: gold, background: `${gold}08` }}>
              <Sparkles size={13} /> SB ME INTELLIGENCE&trade;
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight mb-4" style={{ color: textPrimary }}>
              The <span style={{ color: gold }}>Parlay Builder</span>
            </h2>
            <p className="text-base max-w-2xl mx-auto" style={{ color: textSecondary }}>
              Stack moneyline, spreads, totals, player props, and team props across the SB ME 55-platform catalog — with live odds
              comparison, smart leg validation, and SB ME Intelligence&trade; on every selection. Analytical planning only: SB ME does not accept or place wagers.
            </p>
          </div>

          {/* ── Main grid: demo card + capability list ── */}
          <div className="grid lg:grid-cols-5 gap-10 lg:gap-14 items-start">
            {/* Left: Parlay demo card (spans 2 cols) */}
            <div className="lg:col-span-2">
              <ParlayDemoCard />
              {/* Mini CTA under the card */}
              <div className="mt-5 text-center">
                <Link href="/market-tools/parlay"
                  className="inline-flex items-center gap-2 px-8 py-3.5 rounded-2xl font-extrabold text-sm tracking-wide
                    transition-all duration-200 hover:brightness-110 shadow-[0_4px_28px_rgba(201,168,76,0.40)]"
                  style={{ background: gold, color: navy }}>
                  <Swords size={16} /> BUILD MY PARLAY <ChevronRight size={16} />
                </Link>
                <p className="mt-2 text-[13px]" style={{ color: textSecondary }}>
                  Powered by live odds across 55+ supported platforms. Sign up free to build your first parlay.
                </p>
              </div>
            </div>

            {/* Right: Capability highlights (spans 3 cols) */}
            <div className="lg:col-span-3 space-y-6">
              {/* Capability 1: 55+ Books */}
              <ParlayCapability
                icon={<Building2 size={22} style={{ color: gold }} />}
                title="55+ Sportsbooks & Platforms"
                description="Compare odds across DraftKings, FanDuel, BetMGM, Caesars, ESPN BET, Bovada, Bet365, PointsBet, BetRivers, Pinnacle, Unibet, William Hill, Barstool, Betway, Betfred, Circa, Hard Rock Bet, BetOnline, Polymarket, Bally Bet, and 35+ more (availability varies by sport and event). Find the best line for every leg of your parlay."
              />

              {/* Capability 2: 6 sports */}
              <ParlayCapability
                icon={<Trophy size={22} style={{ color: gold }} />}
                title="17-League Coverage"
                description="Build parlays across all 17 supported Rookie leagues, including MLB, NBA, NFL, NHL, college, WNBA, UFC, and eight soccer competitions (Premier League, Champions League, MLS, La Liga, Bundesliga, Serie A, Ligue 1, International Soccer). Live markets appear only when SportsGameOdds returns them."
              />

              {/* Capability 3: Bet types */}
              <ParlayCapability
                icon={<Target size={22} style={{ color: gold }} />}
                title="Moneyline, Spreads, Totals & Player Props"
                description="Combine any bet type in a single parlay. Stack a moneyline from one game with a player prop from another and a total from a third. The Builder validates every leg and shows you the real multi-leg payout before you lock in."
              />

              {/* Capability 4: SB ME Intelligence */}
              <ParlayCapability
                icon={<Brain size={22} style={{ color: gold }} />}
                title="SB ME Intelligence&trade; Integration"
                description="Every parlay is backed by SB ME's AI-powered analysis. Check player projections, Optimal%, leverage scores, and SB OWN% alongside live odds — so you can build data-driven parlays, not guesses."
              />
            </div>
          </div>

          {/* ── Bookmakers strip ── */}
          <div className="mt-16 pt-10 border-t" style={{ borderColor: border }}>
            <div className="text-center mb-6">
              <h3 className="text-sm font-bold tracking-widest uppercase" style={{ color: textSecondary }}>
                55+ Supported Sportsbooks & Platforms
              </h3>
              <p className="mt-1 text-[13px]" style={{ color: textSecondary }}>
                Live odds comparison across every major operator. Availability varies by sport and event.
              </p>
            </div>
            {/* Scrollable book pill strip */}
            <div className="flex flex-wrap justify-center gap-2 max-w-4xl mx-auto">
              {featuredBooks.map((book) => (
                <BookPill key={book} name={book} />
              ))}
              <span className="inline-flex items-center px-3 py-1.5 rounded-lg text-[11px] font-extrabold"
                style={{ background: `${gold}10`, border: `1px solid ${gold}25`, color: gold }}>
                +35 MORE
              </span>
            </div>
          </div>

          {/* ── Sports coverage grid ── */}
          <div className="mt-12 pt-10 border-t" style={{ borderColor: border }}>
            <div className="text-center mb-6">
              <h3 className="text-sm font-bold tracking-widest uppercase" style={{ color: textSecondary }}>
                Supported Sports & Leagues
              </h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 max-w-5xl mx-auto">
              {coveredSports.map((sport) => (
                <div key={sport.leagueID} className="text-center p-4 rounded-2xl border transition-all hover:border-[#c9a84c30]"
                  style={{ background: cardElevated, borderColor: border }}>
                  <div className="text-sm font-extrabold" style={{ color: textPrimary }}>{sport.name}</div>
                  <div className="text-[10px] font-bold" style={{ color: textMuted }}>{sport.sport}</div>
                </div>
              ))}
            </div>
            <div className="mt-8 text-center">
              <h4 className="text-sm font-bold tracking-widest uppercase mb-3" style={{ color: gold }}>Soccer</h4>
              <p className="text-[13px] mb-4 max-w-xl mx-auto" style={{ color: textSecondary }}>
                Soccer is a first-class part of SB ME market intelligence — separate from DFS slate sports.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {soccerLeagues.map((lg) => (
                  <span key={lg.leagueID} className="px-3 py-1.5 rounded-lg text-[11px] font-bold" style={{ background: cardElevated, border: `1px solid ${border}`, color: textSecondary }}>
                    {lg.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Section>
      </div>

      {/* ═══ INTELLIGENCE ═══ */}
      <Section className="py-20 md:py-24">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight" style={{ color: textPrimary }}>
            Intelligence That Gives<br className="hidden sm:block" /> You an <span style={{ color: gold }}>Edge</span>
          </h2>
          <p className="mt-4 text-base max-w-xl mx-auto" style={{ color: textSecondary }}>
            Data-driven insights across every dimension of your fantasy slate.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
          {[
            {
              icon: Users,
              title: "Player Intelligence",
              desc: "Deep player projections, matchup analysis, and trend detection across every position.",
              chart: <MiniBarChart values={[65,78,82,75,91,88,94,90]} width={100} height={36} />,
              stat: "229 projected",
              statVal: "players",
            },
            {
              icon: BarChart3,
              title: "Game Intelligence",
              desc: "Real-time odds, market intelligence, and line movement analysis for every game.",
              chart: <Sparkline data={[1,2,1.5,3,2.5,4,3.5,5,4.2]} width={100} height={36} stroke={gold} />,
              stat: "50 live",
              statVal: "events tracked",
            },
            {
              icon: Brain,
              title: "AI Insights",
              desc: "Natural language insights, recommended plays, and edge detection from SB ME Intelligence.",
              chart: (
                <div className="flex items-center gap-1">
                  {[8,7,9,8,8].map((v, i) => (
                    <div key={i} className="flex-1 rounded-sm" style={{ height: `${v * 3}px`, background: v >= 8 ? gold : "#334155" }} />
                  ))}
                </div>
              ),
              stat: "24/7",
              statVal: "AI analysis",
            },
          ].map((card, i) => {
            const Icon = card.icon;
            return (
              <div key={i} className="rounded-3xl border p-6 lg:p-7 transition-all duration-300 hover:border-[#c9a84c30] hover:shadow-lg hover:shadow-[#c9a84c08]"
                style={{ background: cardElevated, borderColor: border }}>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${gold}10` }}>
                    <Icon size={20} style={{ color: gold }} />
                  </div>
                  <h3 className="text-base font-extrabold" style={{ color: textPrimary }}>{card.title}</h3>
                </div>
                <p className="text-sm leading-relaxed mb-5" style={{ color: textSecondary }}>{card.desc}</p>

                {/* Chart */}
                <div className="mb-3 flex justify-center">
                  {card.chart}
                </div>

                {/* Stat */}
                <div className="flex items-center justify-between pt-3 border-t" style={{ borderColor: border }}>
                  <span className="text-lg font-extrabold" style={{ color: gold }}>{card.stat}</span>
                  <span className="text-xs" style={{ color: textMuted }}>{card.statVal}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ═══ PRICING ═══ */}
      <div id="pricing" style={{ background: "transparent", borderTop: `1px solid ${border}` }}>
        <Section className="py-20 md:py-24">
          <div className="text-center mb-14">
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight" style={{ color: textPrimary }}>
              Simple, <span style={{ color: gold }}>Transparent</span> Pricing
            </h2>
            <p className="mt-4 text-base max-w-xl mx-auto" style={{ color: textSecondary }}>
              Start free. Upgrade when you need the edge.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8 max-w-4xl mx-auto">
            {([
              { name: "Starter", price: "Free", features: ["1 daily lineup", "MLB projections", "Live scores & market data", "Player props", "AI chat (10 msgs/day)"], cta: "Get Started", href: "/register", featured: false, goldPrice: false, period: null as string | null, annual: null as string | null },
              { name: "Pro Arena", price: "$49", period: ".99/mo", annual: "or $399.99/year", features: ["10 daily lineups", "All-sport DFS projections", "Live odds, Fair Odds & Book Consensus", "Player & team props, alternate lines", "AI chat (unlimited)", "Lineup optimizer", "Stacking rules"], cta: "Start Pro", href: "/register", featured: true, goldPrice: true },
              { name: "Elite Stack", price: "$89", period: ".99/mo", annual: "or $599.99/year", features: ["Unlimited lineups", "All-sport DFS projections", "Custom projections", "Full AI intelligence", "Priority support", "Early features", "Everything in Pro"], cta: "Go Elite", href: "/register", featured: false, goldPrice: false },
            ] as const).map((plan, i) => (
              <div key={i} className={`relative rounded-3xl border p-6 lg:p-8 flex flex-col transition-all duration-300 hover:shadow-xl
                ${plan.featured ? "scale-[1.03] z-10" : ""}`}
                style={{
                  background: plan.featured ? "rgba(16,22,47,0.94)" : "rgba(16,22,47,0.86)",
                  borderColor: plan.featured ? gold : border,
                  borderWidth: plan.featured ? "2px" : "1px",
                }}>
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold tracking-wider"
                    style={{ background: gold, color: navy }}>
                    MOST POPULAR
                  </div>
                )}
                <h3 className="text-sm font-bold tracking-widest uppercase mb-2" style={{ color: textSecondary }}>{plan.name}</h3>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className={`text-4xl font-extrabold`} style={{ color: plan.goldPrice ? gold : textPrimary }}>{plan.price}</span>
                  {plan.period && <span className="text-sm" style={{ color: textMuted }}>{plan.period}</span>}
                </div>
                {plan.annual && (
                  <p className="text-sm mb-1" style={{ color: textMuted }}>{plan.annual}</p>
                )}
                <p className="text-sm mb-6" style={{ color: textSecondary }}>{plan.price === "Free" ? "No credit card required" : "Cancel anytime"}</p>
                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-start gap-2.5 text-sm" style={{ color: textSecondary }}>
                      <Check size={15} className="mt-0.5 shrink-0" style={{ color: gold }} />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link href={plan.href}
                  className={`block text-center py-3 rounded-2xl text-sm font-bold transition-all duration-200`}
                  style={{
                    background: plan.featured ? gold : "transparent",
                    color: plan.featured ? navy : gold,
                    border: plan.featured ? "none" : `1px solid ${gold}`,
                  }}>
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* ═══ CTA BAND ═══ */}
      <Section id="resources" className="py-20 md:py-24">
        <div className="rounded-3xl border p-10 md:p-14 text-center relative overflow-hidden"
          style={{ background: cardElevated, borderColor: border }}>
          <div className="absolute -top-10 -right-10 w-56 h-56 opacity-[0.07] pointer-events-none"
            style={{ background: `radial-gradient(circle, ${gold} 0%, transparent 70%)` }} />
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight mb-4" style={{ color: textPrimary }}>
            Analyze Every Slate with <span style={{ color: gold }}>SB ME Intelligence</span>
          </h2>
          <p className="text-base max-w-lg mx-auto mb-8" style={{ color: textSecondary }}>
            Sports analytics and DFS intelligence software for sharper, more informed decisions.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <GoldButton href="/register">
              <Star size={16} /> Get Started Now
            </GoldButton>
            <GhostButton href="/login">
              Sign In
            </GhostButton>
          </div>
        </div>
      </Section>

      {/* ═══ FOOTER ═══ */}
      <footer id="about" style={{ borderTop: `1px solid ${border}`, background: "rgba(10,15,36,0.78)" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid md:grid-cols-5 gap-8 mb-10">
            {/* Brand */}
            <div>
              <Link href="/" className="inline-block mb-3">
                <Image src="/logo.png" alt="SB ME DFS.AI" width={100} height={53} />
              </Link>
              <p className="text-[13px] leading-relaxed" style={{ color: textSecondary }}>
                AI-powered DFS intelligence platform. Advanced projections, real-time odds, lineup optimization, and AI insights.
              </p>
            </div>

            {/* Links */}
            {[
              ["Product", [
                ["Dashboard", "/dashboard"], ["Optimizer", "/optimizer"], ["Player Props", "/market-tools/player-props"],
                ["Live Odds", "/market-tools/live-odds"], ["Lineups", "/lineups"],
              ]],
              ["Company", [
                ["About", "/about"], ["Blog", "/blog"], ["Careers", "/careers"], ["Contact", "/contact"],
              ]],
              ["Legal", [
                ["Terms of Service", "/terms"], ["Privacy Policy", "/privacy"], ["Refund & Cancellation Policy", "/refund-policy"],
              ]],
            ].map(([heading, links]) => (
              <div key={heading as string}>
                <h4 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: textSecondary }}>{heading as string}</h4>
                <ul className="space-y-2">
                  {(links as [string, string][]).map(([label, href]) => (
                    <li key={label}>
                      <Link href={href} className="text-sm transition-colors duration-150 hover:text-[#c9a84c]" style={{ color: textSecondary }}>{label}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {/* FOLLOW SB ME */}
            <div>
              <h4 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: textSecondary }}>Follow SB ME</h4>
              <ul className="space-y-2.5">
                <li>
                  <a
                    href="https://x.com/SportbookMeAI"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Follow Sportbook Me DFS AI on X"
                    className="inline-flex items-center gap-2 text-sm transition-colors duration-150 hover:text-[#c9a84c]"
                    style={{ color: textMuted }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                    </svg>
                    <span>@SportbookMeAI</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://instagram.com/sbmedfsai"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Follow SB ME DFS AI on Instagram"
                    className="inline-flex items-center gap-2 text-sm transition-colors duration-150 hover:text-[#c9a84c]"
                    style={{ color: textMuted }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>
                    </svg>
                    <span>@sbmedfsai</span>
                  </a>
                </li>
                <li>
                  <a
                    href="https://facebook.com/sbmedfsai"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Follow Sportbook Me DFS AI on Facebook"
                    className="inline-flex items-center gap-2 text-sm transition-colors duration-150 hover:text-[#c9a84c]"
                    style={{ color: textMuted }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                    </svg>
                    <span>Sportbook Me DFS AI</span>
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom */}
          <div className="pt-8 border-t flex flex-col sm:flex-row items-center justify-between gap-3" style={{ borderColor: border }}>
            <p className="text-xs" style={{ color: textMuted }}>
              &copy; {new Date().getFullYear()} SPORTBOOK ME DFS AI LLC. All rights reserved. SB ME Intelligent AI&trade;.
              SB ME is sports analytics and DFS intelligence software. We do not accept wagers, hold betting funds, or place bets.
            </p>
            <div className="flex items-center gap-1">
              <Brain size={14} style={{ color: gold }} />
              <span className="text-xs font-bold" style={{ color: gold }}>SB ME DFS.AI</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
    </SBMEBackground>
  );
}