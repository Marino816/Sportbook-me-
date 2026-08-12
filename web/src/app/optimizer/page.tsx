"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Play, Loader2, Settings2 } from "lucide-react";
import { fetchDFSSlates, fetchDFSSlate, runOptimizer, fetchSubscriptionStatus, type DFSSlateSummary, type DFSSlateDetail, type LineupResponse, type SubscriptionStatus } from "@/lib/api";

export default function OptimizerPage() {
  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [selectedSlate, setSelectedSlate] = useState<DFSSlateSummary | null>(null);
  const [slateDetail, setSlateDetail] = useState<DFSSlateDetail | null>(null);
  const [strategy, setStrategy] = useState("balanced");
  const [lineupCount, setLineupCount] = useState(1);
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchDFSSlates();
        if (res?.data) {
          const published = res.data.filter((s: DFSSlateSummary) => s.status === "PUBLISHED");
          setSlates(published);
          if (published.length > 0) setSelectedSlate(published[0]);
        }
        const subRes = await fetchSubscriptionStatus();
        if (subRes?.data) setSub(subRes.data);
      } catch { /* unavailable */ }
      setLoading(false);
    }
    load();
  }, []);

  useEffect(() => {
    if (!selectedSlate) return;
    async function load() {
      try {
        const res = await fetchDFSSlate(selectedSlate!.id);
        if (res?.data) setSlateDetail(res.data);
      } catch { setSlateDetail(null); }
    }
    load();
  }, [selectedSlate]);

  const maxLineups = sub?.plan === "Elite Stack" ? 150 : sub?.plan === "Pro Arena" ? 20 : 1;
  const platform = selectedSlate?.platform || "draftkings";
  const sport = selectedSlate?.sport || "MLB";

  const optimizeMutation = useMutation({
    mutationFn: () => runOptimizer(selectedSlate!.id, {
      sport,
      platform,
      strategy,
      num_lineups: Math.min(lineupCount, maxLineups),
    }),
  });

  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", display: "flex", flexDirection: "column", color: "#f0f6fc" }}>
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>Lineup Optimizer</h1>
          <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
            Native DFS · CP-SAT Engine · SportsGameOdds Intelligence
          </p>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <div style={{ width: 320, flexShrink: 0, borderRight: "1px solid #1e293b", overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Slate Selector */}
          <section>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>
              <Settings2 size={12} style={{ display: "inline", marginRight: 4 }} />Select Slate
            </p>
            {loading ? (
              <p style={{ color: "#64748b", fontSize: 13 }}>Loading slates...</p>
            ) : slates.length === 0 ? (
              <p style={{ color: "#64748b", fontSize: 13 }}>No published slates available.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {slates.map((s) => (
                  <button key={s.id} onClick={() => setSelectedSlate(s)} style={{
                    padding: "10px 14px", borderRadius: 10, textAlign: "left",
                    background: selectedSlate?.id === s.id ? "rgba(201,168,76,0.1)" : "#0a0f24",
                    border: selectedSlate?.id === s.id ? "1px solid rgba(201,168,76,0.3)" : "1px solid #1e293b",
                    color: selectedSlate?.id === s.id ? "#c9a84c" : "#94a3b8",
                    cursor: "pointer", fontSize: 13, fontWeight: 600,
                  }}>
                    {s.slate_name}
                    <span style={{ display: "block", fontSize: 11, color: "#64748b", marginTop: 2 }}>
                      {s.sport} · {s.platform} · {s.player_count} players
                    </span>
                  </button>
                ))}
              </div>
            )}
            {slateDetail && (
              <p style={{ color: "#c9a84c", fontSize: 12, marginTop: 8 }}>
                DraftKings Contest Data — Powered by SB ME Intelligence
              </p>
            )}
          </section>

          {/* Strategy */}
          <section>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>Strategy</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4 }}>
              {["balanced", "cash", "gpp"].map((s) => (
                <button key={s} onClick={() => setStrategy(s)} style={{
                  padding: "8px", borderRadius: 8, textTransform: "capitalize", fontSize: 12, fontWeight: 700,
                  background: strategy === s ? "rgba(201,168,76,0.15)" : "#0a0f24",
                  border: strategy === s ? "1px solid rgba(201,168,76,0.4)" : "1px solid #1e293b",
                  color: strategy === s ? "#c9a84c" : "#94a3b8", cursor: "pointer",
                }}>{s}</button>
              ))}
            </div>
          </section>

          {/* Lineup Count */}
          <section>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>
              Lineups ({Math.min(lineupCount, maxLineups)}/{maxLineups} allowed)
            </p>
            <input type="range" min={1} max={150} value={lineupCount}
              onChange={(e) => setLineupCount(parseInt(e.target.value))}
              style={{ width: "100%", accentColor: "#c9a84c" }} />
          </section>

          {/* Generate Button */}
          <button onClick={() => optimizeMutation.mutate()} disabled={!selectedSlate || optimizeMutation.isPending}
            style={{
              padding: "14px", borderRadius: 14, fontWeight: 800, fontSize: 15, textTransform: "uppercase",
              background: selectedSlate ? "#c9a84c" : "#1e293b",
              color: selectedSlate ? "#060b1a" : "#64748b",
              border: "none", cursor: selectedSlate ? "pointer" : "not-allowed",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              boxShadow: selectedSlate ? "0 4px 20px rgba(201,168,76,0.3)" : "none",
              marginTop: "auto",
            }}>
            {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" />Solving...</> : <><Play size={18} />Generate {Math.min(lineupCount, maxLineups)} Lineup{lineupCount > 1 ? "s" : ""}</>}
          </button>
        </div>

        {/* Main */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {optimizeMutation.isPending ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300 }}>
              <div style={{ width: 40, height: 40, borderRadius: "50%", border: "4px solid #c9a84c", borderTopColor: "transparent", animation: "spin 1s linear infinite" }} />
              <p style={{ color: "#94a3b8", marginTop: 16, fontWeight: 600 }}>
                Running CP-SAT optimizer for {sport} {platform}...
              </p>
            </div>
          ) : optimizeMutation.isError ? (
            <div style={{ padding: 32, background: "rgba(239,68,68,0.08)", borderRadius: 16, border: "1px solid rgba(239,68,68,0.2)", textAlign: "center" }}>
              <p style={{ fontSize: 18, fontWeight: 800, color: "#ef4444", marginBottom: 8 }}>Generation Failed</p>
              <p style={{ color: "#94a3b8", fontSize: 14 }}>
                {optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Unable to generate lineups."}
              </p>
            </div>
          ) : optimizeMutation.data?.data ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {(optimizeMutation.data.data as LineupResponse[]).map((l: LineupResponse, i: number) => (
                <div key={i} style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden" }}>
                  <div style={{ height: 4, background: "#c9a84c" }} />
                  <div style={{ padding: "16px 20px", borderBottom: "1px solid #1e293b", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontWeight: 800, fontSize: 15, color: "#f0f6fc" }}>Lineup {i + 1}</span>
                      <span style={{ marginLeft: 12, fontSize: 12, color: "#64748b" }}>{sport} · {platform}</span>
                    </div>
                    <div style={{ display: "flex", gap: 16 }}>
                      <span style={{ color: "#94a3b8", fontSize: 13 }}>Salary: <strong style={{ color: "#f0f6fc" }}>${l.total_salary.toLocaleString()}</strong></span>
                      <span style={{ color: "#c9a84c", fontSize: 13, fontWeight: 700 }}>Proj: {l.projected_score}</span>
                    </div>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <tbody>
                      {l.players.map((p, j) => (
                        <tr key={j} style={{ borderBottom: j < l.players.length - 1 ? "1px solid #1e293b30" : "none" }}>
                          <td style={{ padding: "10px 20px", width: 80 }}>
                            <span style={{ fontSize: 11, fontWeight: 700, color: "#c9a84c", textTransform: "uppercase", background: "rgba(201,168,76,0.1)", padding: "3px 8px", borderRadius: 6 }}>
                              {p.roster_position || "?"}
                            </span>
                          </td>
                          <td style={{ padding: "10px 0", fontWeight: 600, color: "#f0f6fc" }}>
                            {p.name || `Player #${p.player_id || p.id}`}
                          </td>
                          <td style={{ padding: "10px 0", color: "#64748b", fontSize: 13, textAlign: "right" }}>
                            {p.team || ""}
                          </td>
                          <td style={{ padding: "10px 20px", fontWeight: 600, color: "#94a3b8", textAlign: "right" }}>
                            ${(p.salary || 0).toLocaleString()}
                          </td>
                          <td style={{ padding: "10px 20px", fontWeight: 700, color: "#c9a84c", textAlign: "right" }}>
                            {(p.projected_fp || 0).toFixed(1)} FP
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ) : selectedSlate ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, textAlign: "center" }}>
              <div style={{ width: 80, height: 80, borderRadius: 20, background: "#0a0f24", border: "1px solid #1e293b", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36, marginBottom: 16 }}>
                ⚾
              </div>
              <h3 style={{ fontSize: 18, fontWeight: 800, color: "#f0f6fc", marginBottom: 8 }}>Ready to Optimize</h3>
              <p style={{ color: "#94a3b8", fontSize: 14, maxWidth: 400 }}>
                Selected: <strong style={{ color: "#c9a84c" }}>{selectedSlate.slate_name}</strong> ({selectedSlate.sport} · {selectedSlate.platform} · {selectedSlate.player_count} players)
              </p>
              <p style={{ color: "#64748b", fontSize: 13, marginTop: 8 }}>Choose a strategy and click Generate.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, textAlign: "center" }}>
              <p style={{ color: "#64748b", fontSize: 16 }}>Select a published DFS slate to begin.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}