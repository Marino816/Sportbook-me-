"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Database, Search, Lock, Ban, Heart, Send, Loader2, BarChart3, Layers, X } from "lucide-react";
import { fetchDataHubSlate, fetchDFSSlates, runSims, type CanonicalPlayer, type DFSSlateSummary } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";
import { PlayerAvatar, TeamLogo } from "@/lib/assets";
import { LastFive } from "@/lib/last-five";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"];
const PLATFORMS = ["draftkings", "fanduel"];
const POSITIONS = ["ALL", "P", "C", "1B", "2B", "3B", "SS", "OF"];

const navy = "#0a0f24";
const cardBg = "#0a0f24";
const gold = "#c9a84c";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export default function DataHubPage() {
  const router = useRouter();
  const ws = useWorkspace();

  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [players, setPlayers] = useState<CanonicalPlayer[]>([]);
  const [meta, setMeta] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [sims, setSims] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");

  const [drawerPlayer, setDrawerPlayer] = useState<CanonicalPlayer | null>(null);

  // Resolve slate on mount / sport+platform change
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        const res = await fetchDFSSlates(ws.platform, ws.sport);
        const published = (res?.data ?? []).filter((s) => s.status === "PUBLISHED");
        if (!cancelled) {
          setSlates(published);
          const chosen = published[0]?.id ?? null;
          if (chosen) ws.setSlateId(chosen);
          else ws.setSlateId(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load slates");
      }
    })();
    return () => { cancelled = true; };
  }, [ws.sport, ws.platform]);

  // Load canonical pool
  useEffect(() => {
    if (!ws.slateId) { setPlayers([]); setMeta(null); return; }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetchDataHubSlate(ws.slateId!, ws.platform);
        if (!cancelled) {
          setPlayers(res?.data?.players ?? []);
          setMeta(res?.data?.metadata ?? null);
          setSims({});
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load data hub");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [ws.slateId, ws.platform]);

  const teamOptions = useMemo(() => {
    const s = new Set<string>();
    for (const p of players) if (p.team) s.add(p.team);
    return Array.from(s).sort();
  }, [players]);

  const filtered = useMemo(() => {
    return players.filter((p) => {
      if (posFilter !== "ALL" && p.roster_position !== posFilter) return false;
      if (teamFilter && p.team !== teamFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!p.name.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [players, posFilter, teamFilter, search]);

  const runSimsForPool = async () => {
    if (!ws.slateId) return;
    setSimLoading(true);
    try {
      const res = await runSims({ slate_id: ws.slateId, platform: ws.platform, n_sims: 2000 });
      const map: Record<string, any> = {};
      for (const sp of res?.data?.players ?? []) {
        map[(sp.name || "").toLowerCase()] = sp;
      }
      setSims(map);
    } catch (e: any) {
      setError(e.message || "Simulation failed");
    } finally {
      setSimLoading(false);
    }
  };

  const fmt = (v: number | null | undefined, digits = 1) => (v == null ? "N/A" : v.toFixed(digits));

  return (
    <div style={{ background: navy, color: textPrimary, minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ padding: "16px 24px", borderBottom: `1px solid ${border}`, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <Database size={20} style={{ color: gold }} />
        <h1 style={{ fontSize: 20, fontWeight: 900, color: gold, margin: 0 }}>DATA HUB</h1>
        <span style={{ color: textMuted, fontSize: 12 }}>· Canonical SB DFS Player Model</span>
        <div style={{ flex: 1 }} />
        <Select label="Sport" value={ws.sport} options={SPORTS} onChange={ws.setSport} />
        <Select label="Platform" value={ws.platform} options={PLATFORMS} onChange={ws.setPlatform} format={(v) => (v === "draftkings" ? "DraftKings" : "FanDuel")} />
        <Select label="Slate" value={ws.slateId == null ? "" : String(ws.slateId)} options={slates.map((s) => String(s.id))} format={(v) => { const s = slates.find((x) => String(x.id) === v); return s ? `${s.sport} ${s.slate_name}` : v; }} onChange={(v) => ws.setSlateId(v ? Number(v) : null)} />
        <span style={{ color: textMuted, fontSize: 11 }}>{meta ? `Updated ${new Date(meta.generated_at).toLocaleTimeString()}` : "—"}</span>
      </div>

      {/* Filters */}
      <div style={{ padding: "10px 24px", borderBottom: `1px solid ${border}`, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        {POSITIONS.map((pos) => (
          <button key={pos} onClick={() => setPosFilter(pos)} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: posFilter === pos ? `${gold}20` : cardBg, border: posFilter === pos ? `1px solid ${gold}` : `1px solid ${border}`, color: posFilter === pos ? gold : textSecondary, cursor: "pointer" }}>{pos}</button>
        ))}
        <Select label="Team" value={teamFilter} options={["", ...teamOptions]} onChange={setTeamFilter} />
        <div style={{ position: "relative", flex: 1, maxWidth: 260 }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: textMuted }} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search players..." style={{ width: "100%", padding: "6px 10px 6px 30px", borderRadius: 8, fontSize: 12, background: cardBg, border: `1px solid ${border}`, color: textPrimary, outline: "none" }} />
        </div>
        <button onClick={runSimsForPool} disabled={simLoading || !ws.slateId} style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: `${gold}15`, border: `1px solid ${gold}50`, color: gold, cursor: simLoading ? "not-allowed" : "pointer" }}>
          {simLoading ? <Loader2 size={14} className="animate-spin" /> : <BarChart3 size={14} />} Run Sims
        </button>
        <button onClick={() => router.push("/optimizer")} style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: gold, border: "none", color: navy, cursor: "pointer" }}>
          <Send size={14} /> Optimizer
        </button>
      </div>

      {error && <div style={{ padding: "12px 24px", color: "#ef4444", fontSize: 13 }}>{error}</div>}

      {/* Table */}
      <div style={{ padding: "0 24px 24px", overflowX: "auto" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}><Loader2 size={28} className="animate-spin" style={{ margin: "0 auto" }} /></div>
        ) : players.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: textMuted }}>No published slate for {ws.sport} ({ws.platform}). Upload a contest salary CSV to populate the Data Hub.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${border}`, position: "sticky", top: 0, background: navy }}>
                {["Player", "Pos", "Team", "Opp", "Salary", "SB Proj", "My Proj", "Value", "Own%", "Leverage", "Optimal%", "Ceiling", "Floor", "Status", ""].map((h) => (
                  <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: textMuted, textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 300).map((p) => {
                const sim = sims[(p.name || "").toLowerCase()];
                const locked = ws.lockedIds.includes(p.name);
                const excluded = ws.excludedIds.includes(p.name);
                const liked = ws.likedIds.includes(p.name);
                const myProj = ws.projOverrides[p.name];
                return (
                  <tr key={p.id} onClick={() => setDrawerPlayer(p)} style={{ borderBottom: `1px solid ${border}40`, cursor: "pointer", background: locked ? `${gold}10` : excluded ? "rgba(239,68,68,0.05)" : "transparent", opacity: excluded ? 0.5 : 1 }}>
                    <td style={{ padding: "8px 10px", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: 8 }}>
                      <PlayerAvatar player={{ name: p.name, player_id: p.id }} size={22} />
                      {p.name}
                    </td>
                    <td style={{ padding: "8px 10px", color: gold, fontWeight: 700, textTransform: "uppercase", fontSize: 10 }}>{p.roster_position}</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <TeamLogo team={{ abbreviation: p.team, name: p.team }} size={16} />
                        {p.team}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px", color: textMuted }}>{p.opponent || "—"}</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>${p.salary.toLocaleString()}</td>
                    <td style={{ padding: "8px 10px", color: p.projection_source === "UNAVAILABLE" ? textMuted : gold, fontWeight: 700 }}>{p.projection_source === "UNAVAILABLE" ? "N/A" : p.projected_fp.toFixed(1)}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <input type="number" step="0.1" value={myProj ?? p.projected_fp} onChange={(e) => ws.setProjOverride(p.name, Number(e.target.value))} onClick={(e) => e.stopPropagation()} style={{ width: 56, padding: "4px 6px", borderRadius: 6, fontSize: 11, background: cardBg, border: `1px solid ${border}`, color: textPrimary, outline: "none" }} />
                    </td>
                    <td style={{ padding: "8px 10px", color: gold }}>{p.value.toFixed(2)}</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(p.sbme_ownership_pct, 1)}%</td>
                    <td style={{ padding: "8px 10px", color: (p.leverage ?? 0) > 0 ? "#4ade80" : "#f87171" }}>{fmt(p.leverage, 1)}</td>
                    <td style={{ padding: "8px 10px", color: sim ? gold : textMuted }}>{sim ? `${sim.optimal_pct.toFixed(1)}%` : "N/A"}</td>
                    <td style={{ padding: "8px 10px", color: textSecondary }}>{fmt(p.ceiling, 1)}</td>
                    <td style={{ padding: "8px 10px", color: textMuted }}>{fmt(p.floor, 1)}</td>
                    <td style={{ padding: "8px 10px", color: p.mapping_status === "MATCHED" ? "#4ade80" : textMuted, fontSize: 10 }}>{p.mapping_status || "UNMATCHED"}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <div style={{ display: "flex", gap: 4 }} onClick={(e) => e.stopPropagation()}>
                        <IconBtn title="Lock" active={locked} onClick={() => ws.toggleLock(p.name)}><Lock size={13} /></IconBtn>
                        <IconBtn title="Exclude" active={excluded} onClick={() => ws.toggleExclude(p.name)}><Ban size={13} /></IconBtn>
                        <IconBtn title="Like" active={liked} onClick={() => ws.toggleLike(p.name)}><Heart size={13} /></IconBtn>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Intelligence Drawer */}
      {drawerPlayer && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 60, display: "flex", justifyContent: "flex-end" }} onClick={() => setDrawerPlayer(null)}>
          <div style={{ width: 380, maxWidth: "90vw", background: cardBg, height: "100%", padding: 24, overflowY: "auto", borderLeft: `1px solid ${border}` }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: gold, margin: 0 }}>{drawerPlayer.name}</h2>
              <button onClick={() => setDrawerPlayer(null)} style={{ background: "none", border: "none", color: textSecondary, cursor: "pointer" }}><X size={18} /></button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <Stat label="Team" value={`${drawerPlayer.team} vs ${drawerPlayer.opponent || "—"}`} />
              <Stat label="Position" value={drawerPlayer.roster_position} />
              <Stat label="Salary" value={`$${drawerPlayer.salary.toLocaleString()}`} />
              <Stat label="SB Projection" value={drawerPlayer.projection_source === "UNAVAILABLE" ? "N/A" : drawerPlayer.projected_fp.toFixed(1)} />
              <Stat label="Value" value={drawerPlayer.value.toFixed(2)} />
              <Stat label="Ownership" value={`${fmt(drawerPlayer.sbme_ownership_pct, 1)}%`} />
              <Stat label="Leverage" value={fmt(drawerPlayer.leverage, 1)} />
              <Stat label="Ceiling / Floor" value={`${fmt(drawerPlayer.ceiling, 0)} / ${fmt(drawerPlayer.floor, 0)}`} />
              <Stat label="Projection Source" value={drawerPlayer.projection_source} />
              <Stat label="Game total (SB ME)" value={drawerPlayer.sbme_game_total != null ? String(drawerPlayer.sbme_game_total) : "N/A"} />
              <Stat label="Implied team total (SB ME)" value={drawerPlayer.sbme_implied_team_total != null ? String(drawerPlayer.sbme_implied_team_total) : "N/A"} />
              <Stat label="Hits O/U" value={drawerPlayer.sgo_prop_lines?.hits_line != null ? String(drawerPlayer.sgo_prop_lines.hits_line) : "N/A"} />
              <Stat label="HR O/U" value={drawerPlayer.sgo_prop_lines?.hr_line != null ? String(drawerPlayer.sgo_prop_lines.hr_line) : "N/A"} />
              <Stat label="K O/U" value={drawerPlayer.sgo_prop_lines?.strikeouts_line != null ? String(drawerPlayer.sgo_prop_lines.strikeouts_line) : "N/A"} />
            </div>
            {drawerPlayer.sbme_environment_note && (
              <p style={{ fontSize: 10, color: textMuted, marginBottom: 12 }}>{drawerPlayer.sbme_environment_note}</p>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <ActionBtn label={ws.lockedIds.includes(drawerPlayer.name) ? "Unlock" : "Lock"} icon={<Lock size={14} />} onClick={() => ws.toggleLock(drawerPlayer.name)} />
              <ActionBtn label={ws.excludedIds.includes(drawerPlayer.name) ? "Un-exclude" : "Exclude"} icon={<Ban size={14} />} onClick={() => ws.toggleExclude(drawerPlayer.name)} />
              <ActionBtn label={ws.likedIds.includes(drawerPlayer.name) ? "Unlike" : "Like"} icon={<Heart size={14} />} onClick={() => ws.toggleLike(drawerPlayer.name)} />
              <ActionBtn label="Send to Optimizer" icon={<Send size={14} />} gold onClick={() => { ws.toggleLock(drawerPlayer.name); router.push("/optimizer"); }} />
            </div>
            <LastFive player={{ name: drawerPlayer.name, player_id: drawerPlayer.sgo_player_id || drawerPlayer.id, sgo_player_id: drawerPlayer.sgo_player_id, team: drawerPlayer.team, sport: ws.sport, slate_id: ws.slateId ?? undefined }} platform={ws.platform} />
          </div>
        </div>
      )}
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 10, background: "#10162f", border: `1px solid ${border}` }}>
      <div style={{ fontSize: 10, color: textMuted, textTransform: "uppercase", fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 800, color: textPrimary, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function IconBtn({ title, active, onClick, children }: { title: string; active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button title={title} onClick={onClick} style={{ padding: 4, borderRadius: 6, background: active ? `${gold}30` : "transparent", border: active ? `1px solid ${gold}` : "1px solid transparent", cursor: "pointer", color: active ? gold : textMuted, display: "flex" }}>{children}</button>
  );
}

function ActionBtn({ label, icon, onClick, gold: isGold }: { label: string; icon: React.ReactNode; onClick: () => void; gold?: boolean }) {
  return (
    <button onClick={onClick} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700, background: isGold ? gold : cardBg, border: isGold ? "none" : `1px solid ${border}`, color: isGold ? navy : textSecondary, cursor: "pointer" }}>{icon}{label}</button>
  );
}