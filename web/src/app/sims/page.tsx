"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, Loader2, Play, Send, Save, ChevronRight } from "lucide-react";
import { runSims, fetchDFSSlates, type SimPlayer, type SimLineupResult, type DFSSlateSummary } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"];
const PLATFORMS = ["draftkings", "fanduel"];

const navy = "#060b1a";
const cardBg = "#0a0f24";
const gold = "#c9a84c";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export default function SimsPage() {
  const router = useRouter();
  const ws = useWorkspace();

  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [players, setPlayers] = useState<SimPlayer[]>([]);
  const [lineups, setLineups] = useState<SimLineupResult[] | null>(null);
  const [meta, setMeta] = useState<any>(null);
  const [nSims, setNSims] = useState(2000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchDFSSlates(ws.platform, ws.sport);
        const published = (res?.data ?? []).filter((s) => s.status === "PUBLISHED");
        if (!cancelled) {
          setSlates(published);
          if (published[0] && ws.slateId == null) ws.setSlateId(published[0].id);
        }
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [ws.sport, ws.platform]);

  const run = async () => {
    if (!ws.slateId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runSims({
        slate_id: ws.slateId,
        platform: ws.platform,
        n_sims: nSims,
        lineups: ws.pendingLineups.length > 0 ? ws.pendingLineups : undefined,
      });
      setPlayers(res?.data?.players ?? []);
      setLineups(res?.data?.lineups ?? null);
      setMeta(res?.data?.metadata ?? null);
    } catch (e: any) {
      setError(e.message || "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  // Auto-run once when slate is available and no results yet
  useEffect(() => {
    if (ws.slateId && players.length === 0 && !loading) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.slateId]);

  const sortedPlayers = useMemo(() => [...players].sort((a, b) => b.sim_score - a.sim_score), [players]);
  const sortedLineups = useMemo(() => (lineups ? [...lineups].sort((a, b) => (b.sim_score ?? 0) - (a.sim_score ?? 0)) : null), [lineups]);

  const fmt = (v: number | null | undefined, d = 1) => (v == null ? "N/A" : v.toFixed(d));

  return (
    <div style={{ background: navy, color: textPrimary, minHeight: "100vh" }}>
      <div style={{ padding: "16px 24px", borderBottom: `1px solid ${border}`, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <BarChart3 size={20} style={{ color: gold }} />
        <h1 style={{ fontSize: 20, fontWeight: 900, color: gold, margin: 0 }}>SB ME SIMS</h1>
        <div style={{ flex: 1 }} />
        <Select label="Sport" value={ws.sport} options={SPORTS} onChange={ws.setSport} />
        <Select label="Platform" value={ws.platform} options={PLATFORMS} onChange={ws.setPlatform} format={(v) => (v === "draftkings" ? "DraftKings" : "FanDuel")} />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: textMuted }}>SIMS</span>
          <input type="number" min={100} max={10000} step={100} value={nSims} onChange={(e) => setNSims(Number(e.target.value))} style={{ width: 80, padding: "6px 8px", borderRadius: 8, fontSize: 12, background: cardBg, border: `1px solid ${border}`, color: textPrimary }} />
        </div>
        <button onClick={run} disabled={loading || !ws.slateId} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: gold, border: "none", color: navy, cursor: "pointer" }}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run Sims
        </button>
      </div>

      {error && <div style={{ padding: "12px 24px", color: "#ef4444", fontSize: 13 }}>{error}</div>}

      {meta && (
        <div style={{ padding: "8px 24px", borderBottom: `1px solid ${border}`, fontSize: 11, color: textMuted }}>
          Model {meta.model} · {meta.n_sims} sims · {meta.correlation_assumption} · Sim ROI: {meta.sim_roi == null ? "N/A (no payout data)" : meta.sim_roi}
        </div>
      )}

      {/* Lineup ranking (from optimizer) */}
      {sortedLineups && sortedLineups.length > 0 && (
        <div style={{ padding: "20px 24px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: textPrimary, margin: 0 }}>Lineup Rankings</h2>
            <span style={{ fontSize: 11, color: textMuted }}>{sortedLineups.length} lineups simulated</span>
            <div style={{ flex: 1 }} />
            <button onClick={() => router.push("/optimizer")} style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: `${gold}15`, border: `1px solid ${gold}50`, color: gold, cursor: "pointer" }}><Send size={14} /> Back to Optimizer</button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${border}` }}>
                  {["Rank", "Lineup", "Sim Score", "Cash %", "Win %", "Sim ROI", ""].map((h) => (
                    <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: textMuted, textTransform: "uppercase" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedLineups.map((lu, i) => (
                  <tr key={lu.lineup_index} style={{ borderBottom: `1px solid ${border}40`, background: i === 0 ? `${gold}10` : "transparent" }}>
                    <td style={{ padding: "8px 10px", color: i === 0 ? gold : textSecondary, fontWeight: 700 }}>{i + 1}</td>
                    <td style={{ padding: "8px 10px", color: textPrimary, fontWeight: 600 }}>Lineup {lu.lineup_index}</td>
                    <td style={{ padding: "8px 10px", color: gold, fontWeight: 700 }}>{fmt(lu.sim_score, 1)}</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(lu.cash_pct, 1)}%</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(lu.win_pct, 1)}%</td>
                    <td style={{ padding: "8px 10px", color: textMuted }}>{lu.sim_roi == null ? "N/A" : lu.sim_roi}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <button onClick={() => setSavedNote(true)} style={{ display: "flex", alignItems: "center", gap: 4, padding: "5px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: cardBg, border: `1px solid ${border}`, color: textSecondary, cursor: "pointer" }}><Save size={12} /> Save</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {savedNote && <div style={{ marginTop: 8, fontSize: 11, color: gold }}>Saved ✓ (lineups persist in optimizer)</div>}
        </div>
      )}

      {/* Player sim metrics */}
      <div style={{ padding: "20px 24px 24px", overflowX: "auto" }}>
        <h2 style={{ fontSize: 16, fontWeight: 800, color: textPrimary, margin: "0 0 12px" }}>Player Simulation Metrics</h2>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}><Loader2 size={28} className="animate-spin" style={{ margin: "0 auto" }} /></div>
        ) : sortedPlayers.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}>No simulation results yet. Run simulations to populate player metrics.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${border}` }}>
                {["Player", "Pos", "Team", "Salary", "Sim Score", "Optimal %", "Top 1%", "Own %", "Leverage"].map((h) => (
                  <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: textMuted, textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedPlayers.slice(0, 200).map((p) => (
                <tr key={p.id} style={{ borderBottom: `1px solid ${border}40` }}>
                  <td style={{ padding: "8px 10px", fontWeight: 700, color: textPrimary }}>{p.name}</td>
                  <td style={{ padding: "8px 10px", color: gold, fontSize: 10, textTransform: "uppercase", fontWeight: 700 }}>{p.position}</td>
                  <td style={{ padding: "8px 10px", color: textSecondary }}>{p.team}</td>
                  <td style={{ padding: "8px 10px", color: textSecondary }}>${p.salary.toLocaleString()}</td>
                  <td style={{ padding: "8px 10px", color: gold, fontWeight: 700 }}>{fmt(p.sim_score, 1)}</td>
                  <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(p.optimal_pct, 1)}%</td>
                  <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(p.top1_pct, 1)}%</td>
                  <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(p.ownership_pct, 1)}%</td>
                  <td style={{ padding: "8px 10px", color: (p.leverage ?? 0) > 0 ? "#4ade80" : "#f87171" }}>{fmt(p.leverage, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Select({ label, value, options, onChange, format }: { label: string; value: string; options: string[]; onChange: (v: string) => void; format?: (v: string) => string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: textMuted, textTransform: "uppercase" }}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{ padding: "7px 10px", borderRadius: 8, fontSize: 12, fontWeight: 600, background: cardBg, border: `1px solid ${border}`, color: gold, cursor: "pointer" }}>
        {options.map((o) => <option key={o} value={o}>{format ? format(o) : o}</option>)}
      </select>
    </div>
  );
}