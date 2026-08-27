"use client";

import { useAuth } from "@/lib/auth";
import { useEffect, useState } from "react";
import { fetchLineupHistory, type LineupHistoryEntry } from "@/lib/api";

export default function LineupsPage() {
  const { user } = useAuth();
  const [history, setHistory] = useState<LineupHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    async function load() {
      try {
        const res = await fetchLineupHistory();
        if (res?.data) setHistory(res.data);
      } catch { /* history unavailable */ }
      setLoading(false);
    }
    load();
  }, [user]);

  if (!user) {
    return (
      <div style={{ background: "#0a0f24", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Lineups</h1>
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8" }}>Sign in to view your saved lineup history.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#0a0f24", minHeight: "100vh", padding: 32, color: "#f0f6fc", maxWidth: 1000, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Lineups</h1>
      <p style={{ color: "#64748b", marginTop: 4, fontSize: 14 }}>Your saved lineup history across all sports and platforms.</p>

      {loading ? (
        <p style={{ color: "#64748b", marginTop: 24 }}>Loading...</p>
      ) : history.length === 0 ? (
        <div style={{ marginTop: 24, padding: 32, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", textAlign: "center" }}>
          <p style={{ color: "#94a3b8", fontSize: 16, marginBottom: 8 }}>No saved lineups yet.</p>
          <p style={{ color: "#64748b", fontSize: 14 }}>
            Head to the{" "}
            <a href="/optimizer" style={{ color: "#c9a84c", fontWeight: 700 }}>Optimizer</a>
            {" "}to build your first lineup.
          </p>
        </div>
      ) : (
        <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 20 }}>
          {history.map((entry) => (
            <div key={entry.id} style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden" }}>
              <div style={{ height: 4, background: "#c9a84c" }} />
              <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #1e293b" }}>
                <div>
                  <span style={{ fontWeight: 800, fontSize: 15, color: "#f0f6fc" }}>
                    {entry.sport} · {entry.platform}
                  </span>
                  <span style={{ marginLeft: 12, fontSize: 12, color: "#64748b" }}>
                    {entry.strategy} · {entry.lineup_count} lineup{entry.lineup_count > 1 ? "s" : ""}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 16 }}>
                  <span style={{ color: "#94a3b8", fontSize: 13 }}>Salary: <strong style={{ color: "#f0f6fc" }}>${(entry.total_salary || 0).toLocaleString()}</strong></span>
                  <span style={{ color: "#c9a84c", fontSize: 13, fontWeight: 700 }}>Proj: {entry.projected_score}</span>
                </div>
              </div>
              <div style={{ padding: "8px 20px" }}>
                <span style={{ fontSize: 11, color: "#64748b" }}>
                  {entry.data_mode || "native"} · {new Date(entry.created_at).toLocaleDateString()}
                </span>
              </div>
              {entry.lineups?.map((lu, li) => (
                <div key={li} style={{ borderTop: "1px solid #1e293b30", padding: "12px 20px" }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8" }}>Lineup {li + 1}</span>
                  <table style={{ width: "100%", marginTop: 8, fontSize: 13, borderCollapse: "collapse" }}>
                    <tbody>
                      {lu.players?.map((p, pi) => (
                        <tr key={pi}>
                          <td style={{ padding: "3px 0", width: 60 }}>
                            <span style={{ color: "#c9a84c", fontWeight: 700, fontSize: 11, textTransform: "uppercase" }}>
                              {p.roster_slot || "?"}
                            </span>
                          </td>
                          <td style={{ padding: "3px 0", color: "#f0f6fc", fontWeight: 600 }}>
                            {p.name || `Player #${p.id}`}
                          </td>
                          <td style={{ padding: "3px 0", color: "#64748b", fontSize: 12, textAlign: "right" }}>
                            {p.team || ""}
                          </td>
                          <td style={{ padding: "3px 20px", color: "#94a3b8", textAlign: "right" }}>
                            ${(p.salary || 0).toLocaleString()}
                          </td>
                          <td style={{ padding: "3px 0", color: "#c9a84c", fontWeight: 700, textAlign: "right" }}>
                            {(p.projected_fp || 0).toFixed(1)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}