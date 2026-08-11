"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { Home, MessageCircle, Flame, List, User } from "lucide-react";

const QUICK = [
  { icon: Flame, label: "Build Best Lineup", href: "/optimizer" },
  { icon: Home, label: "Cash Lineup", href: "/optimizer" },
  { icon: Flame, label: "GPP Lineup", href: "/optimizer" },
  { icon: List, label: "Slate Summary", href: "/lineups" },
  { icon: User, label: "Compare Players", href: "/ai" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.email?.split("@")[0] || "Player";

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 24px", color: "#f0f6fc" }}>
      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: 48 }}>
        <Image src="/logo.png" alt="SB ME DFS.AI" width={200} height={105} priority style={{ margin: "0 auto" }} />
        <p style={{ fontSize: 20, fontWeight: 700, color: "#94a3b8", marginTop: 16 }}>
          Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, {name}.
        </p>
        <p style={{ fontSize: 16, color: "#64748b", marginTop: 4 }}>
          SB ME Intelligent AI™ is ready. AI-Powered DFS Intelligence.
        </p>
        {user && (
          <span style={{ display: "inline-block", marginTop: 12, padding: "6px 16px", borderRadius: 20,
                          background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.3)",
                          color: "#c9a84c", fontSize: 13, fontWeight: 600 }}>
            {user.plan || "Free"} Plan
          </span>
        )}
      </div>

      {/* Quick Actions */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        Quick Actions
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 48 }}>
        {QUICK.map((a, i) => {
          const Icon = a.icon;
          return (
            <Link key={i} href={a.href} style={{
              background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b",
              padding: "24px 16px", textAlign: "center", textDecoration: "none",
              display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
            }}>
              <Icon size={28} color="#c9a84c" />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", lineHeight: 1.3 }}>{a.label}</span>
            </Link>
          );
        })}
      </div>

      {/* SB ME Intelligence */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        SB ME Intelligence
      </h2>
      <div style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 24, marginBottom: 48 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 20 }}>
          {[
            { label: "Top Plays", val: "18", sub: "Strongest market signals" },
            { label: "Best Environment", val: "LAD@SD", sub: "Total 9.5 — HIGH" },
            { label: "Market Edge", val: "+2.3 pts", sub: "Fantasy vs market consensus" },
          ].map((item, i) => (
            <div key={i} style={{
              background: "rgba(201,168,76,0.05)", borderRadius: 14, padding: 16,
              border: "1px solid rgba(201,168,76,0.15)",
            }}>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>{item.label}</span>
              <p style={{ fontSize: 22, fontWeight: 800, color: "#c9a84c", margin: "6px 0" }}>{item.val}</p>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>{item.sub}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SportsGameOdds Integration */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        Powered by SportsGameOdds
      </h2>
      <div style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <span style={{
            background: "rgba(201,168,76,0.15)", color: "#c9a84c", fontWeight: 700, fontSize: 12,
            padding: "4px 12px", borderRadius: 20, textTransform: "uppercase",
          }}>Amateur Tier</span>
          <span style={{ color: "#64748b", fontSize: 13 }}>Free — For testing, prototyping, and initial development</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, fontSize: 13 }}>
          {[
            "2.5k objects/month", "10 req/min", "10 min refresh", "8 Leagues",
            "9 Bookmakers", "Metadata — Sports, Leagues, Teams, Players, Events",
            "Results, Live Scores, Game Status", "Odds — Spreads, Moneylines, Totals",
            "Pregame + Live + Partials", "Fair Odds + Book Consensus",
            "Player Props + Team Props + Alt Lines",
            "DraftKings, FanDuel, BetMGM, Caesars, ESPN BET, Bovada, Unibet",
            "NFL, NBA, MLB, NHL, College FB, College BB, Champions League, MLS",
          ].map((feat, i) => (
            <div key={i} style={{ color: "#94a3b8", padding: "6px 0", borderBottom: "1px solid #1e293b30" }}>
              ✓ {feat}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}