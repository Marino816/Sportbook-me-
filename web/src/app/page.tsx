"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  TrendingUp, Activity, Target, Layers, Bot, Sparkles,
  Users, BarChart3, Brain, Menu, X, ChevronRight, Check,
  ArrowRight, Zap, Star,
} from "lucide-react";

/* ── Brand palette ── */
const navy = "#060b1a";
const cardBg = "#0a0f24";
const cardElevated = "#10162f";
const gold = "#c9a84c";
const goldDim = "#a68a32";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

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

/* ── MAIN PAGE ── */
export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "Resources", href: "#resources" },
    { label: "About", href: "#about" },
  ];

  return (
    <div style={{ background: navy, color: textPrimary, fontFamily: "'Inter', sans-serif" }} className="min-h-screen">

      {/* ═══ HEADER ═══ */}
      <header className="sticky top-0 z-50 border-b" style={{ background: "rgba(6,11,26,0.92)", backdropFilter: "blur(16px)", borderColor: border }}>
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
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden" style={{ height: "100vh" }}>
          <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full opacity-10"
            style={{ background: `radial-gradient(circle, ${gold} 0%, transparent 70%)` }} />
          <div className="absolute bottom-[-10%] right-[-5%] w-[400px] h-[400px] rounded-full opacity-8"
            style={{ background: `radial-gradient(circle, ${gold} 0%, transparent 70%)` }} />
        </div>

        <div className="relative grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left */}
          <div>
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs font-bold tracking-widest mb-6"
              style={{ borderColor: `${gold}40`, color: gold, background: `${gold}08` }}>
              <Sparkles size={13} /> AI-POWERED DFS INTELLIGENCE
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1] mb-4" style={{ color: textPrimary }}>
              Build Smarter.<br />
              <span style={{ color: gold }}>Win More.</span>
            </h1>

            <p className="text-lg font-semibold mb-4" style={{ color: gold }}>
              Powered by SB ME Intelligence.
            </p>

            <p className="text-base max-w-lg mb-8" style={{ color: textSecondary }}>
              Advanced projections, real-time odds, player props, and AI insights — all in one place.
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

          {/* Right — dashboard visual */}
          <div className="relative">
            {/* Main card */}
            <div className="rounded-3xl border overflow-hidden shadow-2xl" style={{ background: cardElevated, borderColor: border }}>
              {/* Card header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: border }}>
                <div className="flex items-center gap-2.5">
                  <div className="live-dot" />
                  <span className="text-xs font-bold tracking-widest" style={{ color: gold }}>LIVE PROJECTIONS</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-md" style={{ background: `${gold}18`, color: gold }}>SB ME INTELLIGENCE</span>
              </div>

              {/* Sport pills */}
              <div className="flex gap-1.5 px-4 py-3 border-b" style={{ borderColor: border }}>
                {["MLB", "NFL", "NBA", "NHL"].map((s) => (
                  <span key={s} className="text-[10px] font-bold px-2.5 py-1 rounded-md"
                    style={{ color: s === "MLB" ? gold : textSecondary, background: s === "MLB" ? `${gold}15` : "transparent", border: s === "MLB" ? `1px solid ${gold}30` : "1px solid transparent" }}>
                    {s}
                  </span>
                ))}
              </div>

              {/* Player projection rows */}
              <div className="px-5 py-3 space-y-3">
                {[
                  { name: "Chris Sale", pos: "P", proj: 36.5, sal: "$9,600", trend: [28,30,33,35,36.5] },
                  { name: "Y. Yamamoto", pos: "P", proj: 37.5, sal: "$10,200", trend: [30,32,35,37,37.5] },
                  { name: "Freddie Freeman", pos: "1B", proj: 16.8, sal: "$5,400", trend: [12,14,15,16,16.8] },
                  { name: "Yainer Diaz", pos: "C", proj: 13.1, sal: "$3,700", trend: [9,10,12,13,13.1] },
                ].map((row, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm" style={{ color: textSecondary }}>
                    <span className="w-6 text-[10px] font-bold uppercase" style={{ color: gold }}>{row.pos}</span>
                    <span className="flex-1 font-semibold" style={{ color: textPrimary }}>{row.name}</span>
                    <span className="text-[11px]" style={{ color: textMuted }}>{row.sal}</span>
                    <span className="font-bold" style={{ color: gold }}>{row.proj}</span>
                    <Sparkline data={row.trend} stroke={gold} />
                  </div>
                ))}
              </div>

              {/* Edge stat card */}
              <div className="mx-5 mb-4 p-3 rounded-xl flex items-center justify-between" style={{ background: `${gold}08`, border: `1px solid ${gold}18` }}>
                <div className="flex items-center gap-2">
                  <Zap size={14} style={{ color: gold }} />
                  <span className="text-xs font-semibold" style={{ color: textPrimary }}>AI EDGE DETECTED</span>
                </div>
                <span className="text-xs font-bold" style={{ color: gold }}>+12.5 EV</span>
              </div>
            </div>

            {/* Floating stat cards */}
            <div className="absolute -bottom-4 -left-6 rounded-2xl border px-4 py-3 shadow-xl hidden lg:block"
              style={{ background: cardBg, borderColor: border }}>
              <div className="text-[10px] font-bold tracking-wider mb-1" style={{ color: textMuted }}>PROJ ACCURACY</div>
              <div className="text-lg font-extrabold" style={{ color: gold }}>92.4%</div>
              <MiniBarChart values={[85,88,87,90,92,91,94,92]} width={72} height={22} />
            </div>
            <div className="absolute -top-4 -right-4 rounded-2xl border px-4 py-3 shadow-xl hidden lg:block"
              style={{ background: cardBg, borderColor: border }}>
              <div className="text-[10px] font-bold tracking-wider mb-1" style={{ color: textMuted }}>COVERED POSITIONS</div>
              <div className="text-lg font-extrabold" style={{ color: gold }}>All 9</div>
              <div className="text-[10px]" style={{ color: textMuted }}>DFS roster slots</div>
            </div>
          </div>
        </div>
      </Section>

      {/* ═══ FEATURE STRIP ═══ */}
      <div id="features" style={{ borderTop: `1px solid ${border}`, borderBottom: `1px solid ${border}`, background: cardBg }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
            {[
              { icon: TrendingUp, title: "AI Projections", desc: "Advanced player projections powered by machine learning and real-time data." },
              { icon: Activity, title: "Real-Time Odds", desc: "Live lines, movement tracking, and sharp insights across sportsbooks." },
              { icon: Target, title: "Player Props", desc: "Deep prop analysis with edge detection and fair value comparison." },
              { icon: Layers, title: "Lineup Optimizer", desc: "Build optimized DFS lineups with CP-SAT solver in seconds." },
              { icon: Bot, title: "SB ME AI", desc: "Ask anything. Get smarter. AI-powered insights 24/7." },
            ].map((f, i) => {
              const Icon = f.icon;
              return (
                <div key={i} className="text-center group">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-3 transition-all duration-200 group-hover:scale-110"
                    style={{ background: `${gold}10`, border: `1px solid ${gold}18` }}>
                    <Icon size={22} style={{ color: gold }} />
                  </div>
                  <h3 className="text-sm font-bold mb-1.5" style={{ color: textPrimary }}>{f.title}</h3>
                  <p className="text-xs leading-relaxed" style={{ color: textMuted }}>{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
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
              desc: "Real-time odds, sharp money tracking, and line movement alerts for every game.",
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
      <div id="pricing" style={{ background: cardBg, borderTop: `1px solid ${border}` }}>
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
              { name: "Starter", price: "Free", features: ["1 daily lineup", "MLB projections", "Real-time odds", "Player props", "AI chat (10 msgs/day)"], cta: "Get Started", href: "/register", featured: false, goldPrice: false, period: null as string | null },
              { name: "Pro Arena", price: "$29", period: "/mo", features: ["10 daily lineups", "All-sport projections", "Live odds & movement", "Player props + edge detection", "AI chat (unlimited)", "Lineup optimizer", "Stacking rules"], cta: "Start Pro", href: "/register", featured: true, goldPrice: true },
              { name: "Elite Stack", price: "$99", period: "/mo", features: ["Unlimited lineups", "All-sport projections", "Custom projections", "Full AI intelligence", "Priority support", "Early features", "Everything in Pro"], cta: "Go Elite", href: "/register", featured: false, goldPrice: false },
            ] as const).map((plan, i) => (
              <div key={i} className={`relative rounded-3xl border p-6 lg:p-8 flex flex-col transition-all duration-300 hover:shadow-xl
                ${plan.featured ? "scale-[1.03] z-10" : ""}`}
                style={{
                  background: plan.featured ? cardElevated : "transparent",
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
                <p className="text-xs mb-6" style={{ color: textMuted }}>{plan.price === "Free" ? "No credit card required" : "Cancel anytime"}</p>
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
          <div className="absolute top-0 right-0 w-48 h-48 opacity-10 pointer-events-none"
            style={{ background: `radial-gradient(circle, ${gold} 0%, transparent 70%)` }} />
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight mb-4" style={{ color: textPrimary }}>
            Ready to <span style={{ color: gold }}>Build Smarter?</span>
          </h2>
          <p className="text-base max-w-lg mx-auto mb-8" style={{ color: textSecondary }}>
            Join thousands of DFS players using SB ME Intelligence to gain an edge.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <GoldButton href="/register">
              <Star size={16} /> Start Free Today
            </GoldButton>
            <GhostButton href="/login">
              Sign In
            </GhostButton>
          </div>
        </div>
      </Section>

      {/* ═══ FOOTER ═══ */}
      <footer id="about" style={{ borderTop: `1px solid ${border}`, background: cardBg }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid md:grid-cols-4 gap-8 mb-10">
            {/* Brand */}
            <div>
              <Link href="/" className="inline-block mb-3">
                <Image src="/logo.png" alt="SB ME DFS.AI" width={100} height={53} />
              </Link>
              <p className="text-xs leading-relaxed" style={{ color: textMuted }}>
                AI-powered DFS intelligence platform. Advanced projections, real-time odds, lineup optimization, and AI insights.
              </p>
            </div>

            {/* Links */}
            {[
              ["Product", ["Dashboard", "Optimizer", "Player Props", "Live Odds", "Lineups"]],
              ["Company", ["About", "Blog", "Careers", "Contact"]],
              ["Legal", ["Terms of Service", "Privacy Policy", "Refund Policy"]],
            ].map(([heading, links]) => (
              <div key={heading as string}>
                <h4 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: textSecondary }}>{heading as string}</h4>
                <ul className="space-y-2">
                  {(links as string[]).map((l) => (
                    <li key={l}><a href="#" className="text-sm transition-colors duration-150 hover:text-[#c9a84c]" style={{ color: textMuted }}>{l}</a></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom */}
          <div className="pt-8 border-t flex flex-col sm:flex-row items-center justify-between gap-3" style={{ borderColor: border }}>
            <p className="text-xs" style={{ color: textMuted }}>
              &copy; {new Date().getFullYear()} SPORTBOOK ME DFS AI LLC. All rights reserved. SB ME Intelligent AI&trade;.
            </p>
            <div className="flex items-center gap-1">
              <Brain size={14} style={{ color: gold }} />
              <span className="text-xs font-bold" style={{ color: gold }}>SB ME DFS.AI</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}