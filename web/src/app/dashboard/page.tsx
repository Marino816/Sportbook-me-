"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { Home, MessageCircle, Flame, List, User, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchDFSSlates, type DFSSlateSummary } from "@/lib/api";

const QUICK = [
  { icon: Flame, label: "Build Lineup", href: "/optimizer" },
  { icon: TrendingUp, label: "Market Tools", href: "/market-tools" },
  { icon: List, label: "Saved Lineups", href: "/lineups" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.email?.split("@")[0] || "Player";
  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchDFSSlates();
        if (res?.data) setSlates(res.data.filter((s: DFSSlateSummary) => s.status === "PUBLISHED"));
      } catch { /* slates unavailable */ }
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 24px", color: "#f0f6fc" }}>
      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: 48 }}>
        <Image src="/logo.png" alt="SB ME DFS.AI" width={200} height={105} priority style={{ margin: "0 auto" }} />
        <p style={{ fontSize: 20, fontWeight: 700, color: "#94a3b8", marginTop: 16 }}>
          Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, {name}.
        </p>
        <p style={{ fontSize: 16, color: "#64748b", marginTop: 4 }}>
          SB ME Intelligent AI™ is ready.
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

      {/* Published DFS Slates */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        Published DFS Slates
      </h2>
      {loading ? (
        <div style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 32, textAlign: "center", color: "#94a3b8" }}>
          Loading slates...
        </div>
      ) : slates.length === 0 ? (
        <div style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 32, textAlign: "center", color: "#64748b" }}>
          No published slates available. Check back soon.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 48 }}>
          {slates.map((s) => (
            <Link key={s.id} href={`/optimizer?slate=${s.id}`} style={{
              background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b",
              padding: "16px 20px", textDecoration: "none",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <span style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>{s.slate_name}</span>
                <span style={{ marginLeft: 12, fontSize: 12, color: "#64748b" }}>
                  {s.sport} · {s.platform}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 13, color: "#c9a84c", fontWeight: 600 }}>{s.player_count} players</span>
                <span style={{ color: "#c9a84c" }}>→</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* SB ME Intelligence Summary */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        SB ME Intelligence
      </h2>
      <div style={{ background: "#0a0f24", borderRadius: 20, border: "1px solid #1e293b", padding: 24 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 20 }}>
          <div style={{ background: "rgba(201,168,76,0.05)", borderRadius: 14, padding: 16, border: "1px solid rgba(201,168,76,0.15)" }}>
            <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Data Provider</span>
            <p style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: "6px 0" }}>SportsGameOdds</p>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>Primary market intelligence</span>
          </div>
          <div style={{ background: "rgba(201,168,76,0.05)", borderRadius: 14, padding: 16, border: "1px solid rgba(201,168,76,0.15)" }}>
            <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>DFS Data</span>
            <p style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: "6px 0" }}>Native DK/FD</p>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>Real contest salaries + positions</span>
          </div>
          <div style={{ background: "rgba(201,168,76,0.05)", borderRadius: 14, padding: 16, border: "1px solid rgba(201,168,76,0.15)" }}>
            <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Optimizer</span>
            <p style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: "6px 0" }}>CP-SAT</p>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>OR-Tools constrained optimization</span>
          </div>
        </div>
      </div>
    </div>
  );
}