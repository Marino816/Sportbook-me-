"use client";

import Link from "next/link";
import { TrendingUp, GitCompare, UserCheck, Calculator, Layers, Building2, Zap, ChevronRight } from "lucide-react";

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
] as const;

function ToolAccent({ id }: { id: (typeof TOOLS)[number]["id"] }) {
  if (id === "live-odds") {
    return <span className="sbme-mtool-hud sbme-mtool-hud--live" aria-hidden>LIVE</span>;
  }
  if (id === "compare") {
    return (
      <span className="sbme-mtool-hud sbme-mtool-hud--compare" aria-hidden>
        <i /><i /><i />
      </span>
    );
  }
  if (id === "bookmakers") {
    return <span className="sbme-mtool-hud sbme-mtool-hud--books" aria-hidden>55</span>;
  }
  if (id === "player-props") {
    return (
      <span className="sbme-mtool-hud sbme-mtool-hud--props" aria-hidden>
        <i /><i />
      </span>
    );
  }
  if (id === "arbitrage") {
    return <span className="sbme-mtool-hud sbme-mtool-hud--arb" aria-hidden>#</span>;
  }
  return (
    <span className="sbme-mtool-hud sbme-mtool-hud--parlay" aria-hidden>
      <i /><i /><i />
    </span>
  );
}

export default function MarketToolsHub() {
  return (
    <div className="sbme-mthub">
      <header className="sbme-mthub-head">
        <span className="sbme-mthub-mark">
          <TrendingUp size={22} />
        </span>
        <div>
          <h1>Market Tools</h1>
          <p>
            Live odds, bookmakers, parlays, and props — canonical SportsGameOdds data. SB ME does not accept or place wagers.
          </p>
        </div>
      </header>

      <h2 className="sbme-mthub-kicker">Available Tools</h2>

      <div className="sbme-mthub-grid">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <Link
              key={tool.id}
              href={tool.href}
              className={`sbme-mtool sbme-mtool--${tool.id}`}
            >
              <span className="sbme-mtool-edge" aria-hidden />
              <span className="sbme-mtool-icon">
                <Icon size={22} />
              </span>
              <ToolAccent id={tool.id} />
              <span className="sbme-mtool-title">{tool.title}</span>
              <span className="sbme-mtool-copy">{tool.subtitle}</span>
            </Link>
          );
        })}
      </div>

      <Link href="/ai" className="sbme-mthub-intel">
        <span className="sbme-mthub-intel-glow" aria-hidden />
        <span className="sbme-mthub-intel-line" aria-hidden />
        <span className="sbme-mthub-intel-icon"><Zap size={18} /></span>
        <div className="sbme-mthub-intel-copy">
          <span className="sbme-mthub-intel-title">SB ME Intelligence™</span>
          <p>AI-powered market signals with fantasy-to-market edge detection</p>
        </div>
        <span className="sbme-mthub-intel-go">
          <ChevronRight size={18} />
        </span>
      </Link>
    </div>
  );
}
