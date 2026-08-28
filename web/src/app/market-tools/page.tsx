"use client";

import Link from "next/link";
import { TrendingUp, GitCompare, UserCheck, Calculator, Layers, Building2, Zap } from "lucide-react";

const TOOLS = [
  {
    id: "live-odds",
    title: "Live Odds",
    subtitle: "Scores, main/alt lines, Fair Odds & consensus from SportsGameOdds",
    icon: TrendingUp,
    href: "/market-tools/live-odds",
  },
  {
    id: "compare",
    title: "Compare Odds",
    subtitle: "Side-by-side prices for books that returned a market",
    icon: GitCompare,
    href: "/market-tools/compare",
  },
  {
    id: "bookmakers",
    title: "Bookmakers",
    subtitle: "Live SGO books plus the SB ME 55-platform catalog",
    icon: Building2,
    href: "/market-tools/bookmakers",
  },
  {
    id: "player-props",
    title: "Player & Team Props",
    subtitle: "Player props and team props with main/alt lines",
    icon: UserCheck,
    href: "/market-tools/player-props",
  },
  {
    id: "arbitrage",
    title: "Arbitrage",
    subtitle: "Auto scanner & manual calculator for arbitrage opportunities",
    icon: Calculator,
    href: "/market-tools/arbitrage",
  },
  {
    id: "parlay",
    title: "Parlay Builder",
    subtitle: "Analytical multi-leg planning — SB ME does not place wagers",
    icon: Layers,
    href: "/market-tools/parlay",
  },
];

export default function MarketToolsHub() {
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 24px" }}>
      {/* Hero */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 36,
          background: "#0a0f24",
          borderRadius: 16,
          border: "1px solid #1e293b",
          padding: "24px 28px",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "rgba(201,168,76,0.1)",
            border: "1px solid rgba(201,168,76,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <TrendingUp size={28} color="#c9a84c" />
        </div>
        <div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 900,
              color: "#c9a84c",
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            Market Tools
          </h1>
          <p style={{ fontSize: 14, color: "#94a3b8", margin: "4px 0 0" }}>
            Live odds, bookmakers, parlays, and props — canonical SportsGameOdds data. SB ME does not accept or place wagers.
          </p>
        </div>
      </div>

      {/* Tool Grid */}
      <h2
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 2,
          marginBottom: 16,
        }}
      >
        Available Tools
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 16,
          marginBottom: 40,
        }}
      >
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <Link
              key={tool.id}
              href={tool.href}
              style={{
                background: "#0a0f24",
                borderRadius: 16,
                border: "1px solid #1e293b",
                padding: "24px 20px",
                textDecoration: "none",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                textAlign: "center",
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "#c9a84c";
                (e.currentTarget as HTMLElement).style.background = "rgba(201,168,76,0.05)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "#1e293b";
                (e.currentTarget as HTMLElement).style.background = "#0a0f24";
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 16,
                  background: "rgba(201,168,76,0.1)",
                  border: "1px solid rgba(201,168,76,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 14,
                }}
              >
                <Icon size={28} color="#c9a84c" />
              </div>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#f0f6fc",
                  marginBottom: 6,
                }}
              >
                {tool.title}
              </span>
              <span style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5 }}>
                {tool.subtitle}
              </span>
            </Link>
          );
        })}
      </div>

      {/* Market Intel CTA */}
      <Link
        href="/ai"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          background: "#0a0f24",
          borderRadius: 14,
          border: "1px solid rgba(201,168,76,0.2)",
          padding: "20px 24px",
          textDecoration: "none",
          transition: "all 0.15s",
        }}
      >
        <Zap size={22} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>
            SB ME Intelligence™
          </span>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            AI-powered market signals with fantasy-to-market edge detection
          </p>
        </div>
        <span style={{ color: "#c9a84c", fontSize: 18 }}>→</span>
      </Link>
    </div>
  );
}