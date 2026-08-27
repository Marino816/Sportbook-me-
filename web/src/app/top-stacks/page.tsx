"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Layers, Loader2, Lock, Ban, Send, ChevronDown, ChevronUp } from "lucide-react";
import { fetchTopStacks, fetchDFSSlates, type TopStack, type DFSSlateSummary } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"];
const PLATFORMS = ["draftkings", "fanduel"];

const navy = "#0a0f24";
const cardBg = "#0a0f24";
const gold = "#c9a84c";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export default function TopStacksPage() {
  const router = useRouter();
  const ws = useWorkspace();

  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [stacks, setStacks] = useState<TopStack[]>([]);
  const [meta, setMeta] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sizeFilter, setSizeFilter] = useState<number>(0);

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

  useEffect(() => {
    if (!ws.slateId) { setStacks([]); return; }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetchTopStacks(ws.slateId!, ws.platform);
        if (!cancelled) {
          setStacks(res?.data?.stacks ?? []);
          setMeta(res?.data?.metadata ?? null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load stacks");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [ws.slateId, ws.platform]);

  const filtered = useMemo(() => {
    return sizeFilter === 0 ? stacks : stacks.filter((s) => s.stack_size === sizeFilter);
  }, [stacks, sizeFilter]);

  // Group by team to show best stack per team + all sizes
  const teamBest = useMemo(() => {
    const map = new Map<string, TopStack>();
    for (const s of filtered) {
      const existing = map.get(s.team);
      if (!existing || s.sb_projection > existing.sb_projection) map.set(s.team, s);
    }
    return Array.from(map.values()).sort((a, b) => b.sb_projection - a.sb_projection);
  }, [filtered]);

  const fmt = (v: number | null | undefined, d = 1) => (v == null ? "N/A" : v.toFixed(d));

  const sendStackToOptimizer = (stack: TopStack, lock: boolean) => {
    // Lock/exclude the stack's players in shared state, then navigate
    for (const p of stack.players) {
      if (lock) ws.toggleLock(p.name);
      else ws.toggleExclude(p.name);
    }
    router.push("/optimizer");
  };

  return (
    <div style={{ background: navy, color: textPrimary, minHeight: "100vh" }}>
      <div style={{ padding: "16px 24px", borderBottom: `1px solid ${border}`, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <Layers size={20} style={{ color: gold }} />
        <h1 style={{ fontSize: 20, fontWeight: 900, color: gold, margin: 0 }}>TOP STACKS</h1>
        <div style={{ flex: 1 }} />
        <Select label="Sport" value={ws.sport} options={SPORTS} onChange={ws.setSport} />
        <Select label="Platform" value={ws.platform} options={PLATFORMS} onChange={ws.setPlatform} format={(v) => (v === "draftkings" ? "DraftKings" : "FanDuel")} />
        <div style={{ display: "flex", gap: 4 }}>
          {[0, 5, 4, 3].map((sz) => (
            <button key={sz} onClick={() => setSizeFilter(sz)} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: sizeFilter === sz ? `${gold}20` : cardBg, border: sizeFilter === sz ? `1px solid ${gold}` : `1px solid ${border}`, color: sizeFilter === sz ? gold : textSecondary, cursor: "pointer" }}>{sz === 0 ? "All" : `${sz}-man`}</button>
          ))}
        </div>
      </div>

      {meta && <div style={{ padding: "8px 24px", borderBottom: `1px solid ${border}`, fontSize: 11, color: textMuted }}>Model {meta.model} · {meta.stack_count} stacks · {meta.implied_total}</div>}
      {error && <div style={{ padding: "12px 24px", color: "#ef4444", fontSize: 13 }}>{error}</div>}

      <div style={{ padding: "0 24px 24px", overflowX: "auto" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}><Loader2 size={28} className="animate-spin" style={{ margin: "0 auto" }} /></div>
        ) : teamBest.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}>No stacks available for this slate.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${border}` }}>
                {["", "Team", "Opp", "Implied", "SB Proj", "Own %", "Optimal %", "Leverage", "Value", "Rating", "Actions"].map((h) => (
                  <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: textMuted, textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {teamBest.map((s) => {
                const isOpen = expanded === s.team;
                const teamStacks = stacks.filter((x) => x.team === s.team);
                return (
                  <StackRow key={s.team} stack={s} isOpen={isOpen} onToggle={() => setExpanded(isOpen ? null : s.team)}
                    onLock={() => sendStackToOptimizer(s, true)} onExclude={() => sendStackToOptimizer(s, false)}>
                    {isOpen && (
                      <tr>
                        <td colSpan={11} style={{ padding: "0 12px 16px", background: cardBg }}>
                          {teamStacks.sort((a, b) => b.stack_size - a.stack_size).map((ts) => (
                            <div key={`${ts.team}-${ts.stack_size}`} style={{ padding: "8px 0", borderBottom: `1px solid ${border}30` }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 800, color: gold }}>{ts.stack_size}-man</span>
                                <span style={{ fontSize: 11, color: textMuted }}>${ts.salary.toLocaleString()} · {fmt(ts.sb_projection, 1)} FP · {fmt(ts.stack_ownership, 1)}% own</span>
                                <div style={{ flex: 1 }} />
                                <button onClick={() => sendStackToOptimizer(ts, true)} style={{ fontSize: 10, color: gold, background: "none", border: "none", cursor: "pointer" }}>Lock stack</button>
                              </div>
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                {ts.players.map((p) => (
                                  <span key={p.id} style={{ padding: "4px 8px", borderRadius: 6, fontSize: 10, background: "#10162f", border: `1px solid ${border}`, color: textSecondary }}>
                                    <strong style={{ color: gold }}>{p.position}</strong> {p.name}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </td>
                      </tr>
                    )}
                  </StackRow>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StackRow({ stack: s, isOpen, onToggle, onLock, onExclude, children }: { stack: TopStack; isOpen: boolean; onToggle: () => void; onLock: () => void; onExclude: () => void; children: React.ReactNode }) {
  return (
    <>
      <tr style={{ borderBottom: `1px solid ${border}40`, cursor: "pointer" }} onClick={onToggle}>
        <td style={{ padding: "8px 10px" }}>{isOpen ? <ChevronUp size={14} style={{ color: gold }} /> : <ChevronDown size={14} style={{ color: textMuted }} />}</td>
        <td style={{ padding: "8px 10px", fontWeight: 700, color: textPrimary }}>{s.team}</td>
        <td style={{ padding: "8px 10px", color: textMuted }}>{s.opponent || "—"}</td>
        <td style={{ padding: "8px 10px", color: textMuted }}>{s.implied_total == null ? "N/A" : s.implied_total}</td>
        <td style={{ padding: "8px 10px", color: gold, fontWeight: 700 }}>{s.sb_projection.toFixed(1)}</td>
        <td style={{ padding: "8px 10px", color: textSecondary }}>{s.stack_ownership.toFixed(1)}%</td>
        <td style={{ padding: "8px 10px", color: s.optimal_stack_pct == null ? textMuted : textSecondary }}>{s.optimal_stack_pct == null ? "N/A" : `${s.optimal_stack_pct.toFixed(1)}%`}</td>
        <td style={{ padding: "8px 10px", color: (s.leverage ?? 0) > 0 ? "#4ade80" : "#f87171" }}>{s.leverage.toFixed(1)}</td>
        <td style={{ padding: "8px 10px", color: textSecondary }}>{s.value.toFixed(2)}</td>
        <td style={{ padding: "8px 10px", color: gold, fontWeight: 800 }}>{s.rating}</td>
        <td style={{ padding: "8px 10px" }} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: "flex", gap: 4 }}>
            <button title="Lock stack" onClick={onLock} style={{ padding: 5, borderRadius: 6, background: "transparent", border: "none", color: gold, cursor: "pointer", display: "flex" }}><Lock size={13} /></button>
            <button title="Exclude stack" onClick={onExclude} style={{ padding: 5, borderRadius: 6, background: "transparent", border: "none", color: "#ef4444", cursor: "pointer", display: "flex" }}><Ban size={13} /></button>
            <button title="Send to Optimizer" onClick={onLock} style={{ padding: 5, borderRadius: 6, background: "transparent", border: "none", color: gold, cursor: "pointer", display: "flex" }}><Send size={13} /></button>
          </div>
        </td>
      </tr>
      {children}
    </>
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