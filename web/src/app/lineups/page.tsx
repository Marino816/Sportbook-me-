"use client";

import { useAuth } from "@/lib/auth";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useRouter } from "next/navigation";
import {
  fetchLineupHistory,
  deleteLineupHistory,
  type LineupHistoryEntry,
} from "@/lib/api";

const PAGE_SIZE = 10;
const MAX_PAGES = 2;
const MAIN_CAP = PAGE_SIZE * MAX_PAGES;

function platformLabel(p: string | undefined | null): string {
  const v = (p || "").toLowerCase();
  if (v === "draftkings") return "DraftKings";
  if (v === "fanduel") return "FanDuel";
  return p || "—";
}

function slateLabel(entry: LineupHistoryEntry): string {
  if (entry.slate_name) return entry.slate_name;
  if (entry.slate_unavailable || entry.slate_id) return "Slate unavailable";
  return "Slate unavailable";
}

function buildFromHref(entry: LineupHistoryEntry, lock: boolean): string {
  const params = new URLSearchParams();
  if (entry.sport) params.set("sport", entry.sport);
  if (entry.platform) params.set("platform", entry.platform);
  if (entry.slate_id && !entry.slate_unavailable) params.set("slate", String(entry.slate_id));
  if (lock) {
    const names = (entry.lineups?.[0]?.players || []).map((p) => p.name).filter(Boolean);
    if (names.length) params.set("lock", names.join(","));
  }
  const qs = params.toString();
  return qs ? `/optimizer?${qs}` : "/optimizer";
}

export default function LineupsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [history, setHistory] = useState<LineupHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    async function load() {
      try {
        const res = await fetchLineupHistory(false);
        if (res?.data) setHistory(res.data);
      } catch { /* history unavailable */ }
      setLoading(false);
    }
    load();
  }, [user]);

  const main = history.slice(0, MAIN_CAP);
  const archived = history.slice(MAIN_CAP);
  const visibleSource = showArchived ? archived : main;
  const pageCount = Math.min(MAX_PAGES, Math.max(1, Math.ceil(visibleSource.length / PAGE_SIZE)));
  const safePage = Math.min(page, pageCount);
  const pageRows = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return visibleSource.slice(start, start + PAGE_SIZE);
  }, [visibleSource, safePage]);

  async function onDelete(id: number) {
    setDeleting(true);
    try {
      await deleteLineupHistory(id);
      setHistory((prev) => prev.filter((e) => e.id !== id));
      setConfirmId(null);
    } catch { /* keep card */ }
    setDeleting(false);
  }

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

      <div style={{ marginTop: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button
          onClick={() => { setShowArchived(false); setPage(1); }}
          style={{ padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700, background: !showArchived ? "rgba(201,168,76,0.15)" : "#0a0f24", border: !showArchived ? "1px solid #c9a84c" : "1px solid #1e293b", color: !showArchived ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}
        >
          Recent
        </button>
        {archived.length > 0 && (
          <button
            onClick={() => { setShowArchived(true); setPage(1); }}
            style={{ padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700, background: showArchived ? "rgba(201,168,76,0.15)" : "#0a0f24", border: showArchived ? "1px solid #c9a84c" : "1px solid #1e293b", color: showArchived ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}
          >
            Archived ({archived.length})
          </button>
        )}
        <span style={{ fontSize: 11, color: "#64748b" }}>
          {showArchived ? "Older records stay in your account. Nothing is deleted by paging." : `Showing up to ${MAIN_CAP} newest lineups across two pages.`}
        </span>
      </div>

      {loading ? (
        <p style={{ color: "#64748b", marginTop: 24 }}>Loading...</p>
      ) : visibleSource.length === 0 ? (
        <div style={{ marginTop: 24, padding: 32, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", textAlign: "center" }}>
          <p style={{ color: "#94a3b8", fontSize: 16, marginBottom: 8 }}>{showArchived ? "No archived lineups." : "No saved lineups yet."}</p>
          {!showArchived && (
            <p style={{ color: "#64748b", fontSize: 14 }}>
              Head to the{" "}
              <a href="/optimizer" style={{ color: "#c9a84c", fontWeight: 700 }}>Optimizer</a>
              {" "}to build your first lineup.
            </p>
          )}
        </div>
      ) : (
        <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 20 }}>
          {pageRows.map((entry) => (
            <div key={entry.id} style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden" }}>
              <div style={{ height: 4, background: "#c9a84c" }} />
              <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap", borderBottom: "1px solid #1e293b" }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 15, color: "#f0f6fc" }}>
                    {entry.sport || "—"} · {platformLabel(entry.platform)}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>
                    <div>Slate: {slateLabel(entry)}</div>
                    <div>Strategy: {entry.strategy || "—"}</div>
                    <div>
                      Salary: <strong style={{ color: "#f0f6fc" }}>${(entry.total_salary || 0).toLocaleString()}</strong>
                      {" · "}
                      Projection: <strong style={{ color: "#c9a84c" }}>{entry.projected_score != null ? Number(entry.projected_score).toFixed(1) : "—"}</strong>
                    </div>
                    <div>Saved: {entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button onClick={() => router.push(buildFromHref(entry, false))} style={btnStyle}>Open</button>
                  <button onClick={() => router.push(buildFromHref(entry, true))} style={btnStyle}>Duplicate / Build From</button>
                  <button onClick={() => setConfirmId(entry.id)} style={{ ...btnStyle, color: "#ef4444", borderColor: "rgba(239,68,68,0.35)" }}>Delete</button>
                </div>
              </div>
              {confirmId === entry.id && (
                <div style={{ padding: "12px 20px", background: "rgba(239,68,68,0.06)", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 13, color: "#f0f6fc" }}>Delete this saved lineup?</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button onClick={() => setConfirmId(null)} disabled={deleting} style={btnStyle}>Cancel</button>
                    <button onClick={() => onDelete(entry.id)} disabled={deleting} style={{ ...btnStyle, background: "#ef4444", color: "#fff", borderColor: "#ef4444" }}>{deleting ? "Deleting…" : "Delete"}</button>
                  </div>
                </div>
              )}
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
          {pageCount > 1 && (
            <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
              <button onClick={() => setPage(1)} disabled={safePage === 1} style={btnStyle}>Page 1 — newest</button>
              <button onClick={() => setPage(2)} disabled={safePage === 2 || pageCount < 2} style={btnStyle}>Page 2 — older</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const btnStyle: CSSProperties = {
  padding: "8px 12px",
  borderRadius: 10,
  fontSize: 12,
  fontWeight: 700,
  background: "#0a0f24",
  border: "1px solid #1e293b",
  color: "#c9a84c",
  cursor: "pointer",
};
